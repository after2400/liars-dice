from math import comb

from game.components.bets import Bet
from game.components.context import GameContext


class Stewie:
    """
    Cunning and calculating. Stewie builds a live model of each opponent as
    games progress — tracking who bluffs on which faces, how aggressively
    they open, and whether the table is passive or combative. Every decision
    (when to call, how high to open, which face to raise on) is adjusted in
    real time based on accumulated evidence rather than fixed constants.
    """

    name = "Stewie"

    # --- Tunable parameters ---

    # Call liar when P(bet holds) drops below this (before bluff/velocity adjustments).
    # Sweep-optimised at 0.22 vs PRM field; lower = more conservative, higher = more aggressive.
    BASE_CALL_THRESHOLD = 0.22

    # Floor for the adaptive call threshold — never call with less than this probability,
    # even against a confirmed serial bluffer.
    MIN_CALL_THRESHOLD = 0.10

    # How much a bidder's bluff signal shifts the call threshold.
    # At 0.5 (neutral signal) there is no shift; known bluffers raise it, tight players lower it.
    BLUFF_SENSITIVITY = 0.5

    # Weight given to the face-specific bluff rate vs. the overall bluff rate (remainder).
    # Higher = trust per-face evidence more; lower = fall back to overall rate sooner.
    FACE_BLUFF_WEIGHT = 0.15

    # Each unit of round velocity above 1.0 tightens the call threshold by this much.
    # Velocity = avg quantity increment per bid this round; fast rounds signal overextension.
    VELOCITY_SENSITIVITY = 0.02

    # Default opening factor when no stats are available:
    # quantity = own_count + unseen_expected * OPENING_FACTOR_DEFAULT
    OPENING_FACTOR_DEFAULT = 0.8

    # Pivot challenge-rate used to adjust opening aggression.
    # Below this → table is passive → open higher; above → aggressive → open lower.
    OPENING_CR_PIVOT = 0.22

    # How strongly the table's avg challenge rate shifts the opening factor.
    OPENING_CR_SENSITIVITY = 2.0

    # Clamps for the opening factor (min, max).
    OPENING_FACTOR_MIN = 0.5
    OPENING_FACTOR_MAX = 1.1

    # Score weight for own dice count when choosing which face to raise on.
    RAISE_OWN_WEIGHT = 2.0

    # Score penalty per unit of opponent face-bias when choosing which face to raise on.
    # Higher = more strongly avoid faces opponents are biased toward.
    RAISE_BIAS_PENALTY = 3.0

    # --- Core logic ---

    def _wilds_active(self, prior_bet, bet_history) -> bool:
        if prior_bet is None or not bet_history:
            return True
        current_game = bet_history[-1]["game"]
        current_round = bet_history[-1]["round"]
        for entry in reversed(bet_history):
            if entry["game"] != current_game or entry["round"] != current_round:
                break
            if entry["bet"].face == 1:
                return False
        return True

    def _prob_holds(
        self, hand: list, face: int, quantity: int, total_dice: int, wilds: bool = True
    ) -> float:
        own = hand.count(face) + (hand.count(1) if face != 1 and wilds else 0)
        unseen = total_dice - len(hand)
        p = 1 / 6 if (face == 1 or not wilds) else 2 / 6
        need = quantity - own
        if need <= 0:
            return 1.0
        if need > unseen:
            return 0.0
        return sum(
            comb(unseen, k) * (p**k) * ((1 - p) ** (unseen - k)) for k in range(need, unseen + 1)
        )

    def _call_threshold(self, bidder: str, face: int, stats) -> float:
        """
        Adaptive call threshold based on:
        - Face-specific bluff rate for this bidder (more precise than overall rate)
        - Overall bluff rate as a fallback / blending weight
        - Round velocity: fast-escalating rounds signal overextension → call sooner
        """
        if stats is None:
            return self.BASE_CALL_THRESHOLD

        face_bluff = stats.bluff_rate_by_face.get(bidder, {}).get(face)
        overall_bluff = stats.bluff_rate.get(bidder)

        if face_bluff is not None and overall_bluff is not None:
            bluff_signal = (
                self.FACE_BLUFF_WEIGHT * face_bluff + (1 - self.FACE_BLUFF_WEIGHT) * overall_bluff
            )
        elif overall_bluff is not None:
            bluff_signal = overall_bluff
        else:
            bluff_signal = 0.5  # no data yet — neutral

        bluff_adj = (bluff_signal - 0.5) * self.BLUFF_SENSITIVITY

        velocity = stats.current_round_velocity
        velocity_adj = max(0.0, velocity - 1.0) * self.VELOCITY_SENSITIVITY

        return max(self.MIN_CALL_THRESHOLD, self.BASE_CALL_THRESHOLD + bluff_adj + velocity_adj)

    def _opening_factor(self, stats) -> float:
        """
        Scales how much of the expected-others count to add when opening.
        Passive table (low avg challenge rate) → open higher, they won't call.
        Aggressive table (high avg challenge rate) → open lower, don't overextend.
        """
        if stats is None or not stats.challenge_rate:
            return self.OPENING_FACTOR_DEFAULT

        avg_cr = sum(stats.challenge_rate.values()) / len(stats.challenge_rate)
        adjustment = (self.OPENING_CR_PIVOT - avg_cr) * self.OPENING_CR_SENSITIVITY
        return max(
            self.OPENING_FACTOR_MIN,
            min(self.OPENING_FACTOR_MAX, self.OPENING_FACTOR_DEFAULT + adjustment),
        )

    def _avg_opponent_face_bias(self, face: int, stats) -> float:
        """Average fraction of bids opponents place on this face."""
        if stats is None or not stats.face_bias:
            return 1 / 6
        biases = [pb.get(face, 1 / 6) for pb in stats.face_bias.values()]
        return sum(biases) / len(biases)

    def _best_raise(
        self, hand: list, prior_bet: Bet, stats, wilds: bool = True
    ) -> tuple[int, int] | None:
        """
        Choose the best (quantity, face) raise.

        Candidates: same face +1 quantity (if we hold it), or higher face same
        quantity (if we hold it). Score each by how much we hold vs. how much
        opponents are biased toward that face — prefer faces opponents avoid,
        since our claim is harder to disbelieve.
        """
        candidates = []

        own_on_face = hand.count(prior_bet.face) + (
            hand.count(1) if prior_bet.face != 1 and wilds else 0
        )
        if own_on_face > 0:
            bias = self._avg_opponent_face_bias(prior_bet.face, stats)
            candidates.append((prior_bet.quantity + 1, prior_bet.face, own_on_face, bias))

        for face in range(prior_bet.face + 1, 7):
            own = hand.count(face) + (hand.count(1) if wilds else 0)
            if own > 0:
                bias = self._avg_opponent_face_bias(face, stats)
                candidates.append((prior_bet.quantity, face, own, bias))

        if not candidates:
            return None

        best = max(
            candidates, key=lambda c: c[2] * self.RAISE_OWN_WEIGHT - c[3] * self.RAISE_BIAS_PENALTY
        )
        return best[0], best[1]

    def algo(self, ctx: GameContext) -> Bet | None:
        hand = ctx.hand
        prior_bet = ctx.prior_bet
        total_dice = ctx.total_dice
        bet_history = ctx.bet_history
        stats = ctx.stats

        if prior_bet is None:
            best_face = max(range(2, 7), key=lambda f: hand.count(f) + hand.count(1))
            own = hand.count(best_face) + hand.count(1)
            unseen = total_dice - len(hand)
            factor = self._opening_factor(stats)
            quantity = max(1, round(own + unseen * (2 / 6) * factor))
            return Bet(quantity, best_face, self.name)

        wilds = self._wilds_active(prior_bet, bet_history)
        p_holds = self._prob_holds(hand, prior_bet.face, prior_bet.quantity, total_dice, wilds)
        threshold = self._call_threshold(prior_bet.player, prior_bet.face, stats)
        if p_holds < threshold:
            return None

        raise_result = self._best_raise(hand, prior_bet, stats, wilds)
        if raise_result is not None:
            return Bet(raise_result[0], raise_result[1], self.name)

        # Nothing useful in hand — minimal raise
        return Bet(prior_bet.quantity + 1, prior_bet.face, self.name)
