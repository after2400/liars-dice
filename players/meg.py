from math import comb

from game.components.bets import Bet
from game.components.context import GameContext


class Meg:
    name = "Meg Griffin"

    # ── Tunable parameters ───────────────────────────────────────────────────

    BASE_THRESHOLD = 0.33  # fallback for _estimate_threshold (no stats)
    CR_INTERCEPT = 0.15  # opponent threshold = CR_INTERCEPT + challenge_rate * CR_SLOPE
    CR_SLOPE = 0.80
    DICE_DESPERATION_BOOST = 0.05  # added to threshold per die below a full stack of 5
    BASE_CALL_THRESHOLD = 0.22  # challenge prior bid when p_holds drops below this
    BLUFF_SENSITIVITY = 0.40
    VELOCITY_SENSITIVITY = 0.06  # threshold shift per unit of round velocity above 1.0
    FACE_REVEAL_SENSITIVITY = 0.40  # scale for revealed-hand face frequency bias
    ATTRITION_OPENING_BASE = 0.70  # conservative open factor in large-field attrition mode
    BASE_OPENING_FACTOR = 0.85  # sniper-mode open baseline
    OPENING_CR_PIVOT = 0.22
    OPENING_CR_SENSITIVITY = 1.5
    OPENING_FACTOR_MIN = 0.55
    OPENING_FACTOR_MAX = 1.05
    MEAN_HELD_WEIGHT = 1.0
    RAISE_PROB_WEIGHT = 3.0  # weight for hold probability in raise candidate scoring
    AGGRESSIVE_JUMP_FLOOR = 0.50  # min p_holds at qty+2 to take the backed aggressive jump
    ATTRITION_THRESHOLD = 4  # use attrition mode when player count > this

    # ── Probability core ─────────────────────────────────────────────────────

    def _prob_bet_holds(self, hand: list[int], face: int, quantity: int, total_dice: int) -> float:
        own = hand.count(face) + (hand.count(1) if face != 1 else 0)
        unseen = total_dice - len(hand)
        p = 1 / 6 if face == 1 else 2 / 6
        need = quantity - own
        if need <= 0:
            return 1.0
        if need > unseen:
            return 0.0
        return sum(
            comb(unseen, k) * (p**k) * ((1 - p) ** (unseen - k)) for k in range(need, unseen + 1)
        )

    def _estimate_threshold(self, player: str, stats) -> float:
        cr = stats.challenge_rate.get(player) if stats is not None else None
        base = self.CR_INTERCEPT + cr * self.CR_SLOPE if cr is not None else self.BASE_THRESHOLD
        dice = getattr(stats, "dice_counts", {}).get(player) if stats is not None else None
        desperation = (5 - dice) * self.DICE_DESPERATION_BOOST if dice is not None else 0.0
        return max(0.15, min(0.45, base + desperation))

    def _follower_threshold(self, round_players: list[str], stats) -> float:
        try:
            idx = round_players.index(self.name)
        except ValueError:
            return self.BASE_THRESHOLD
        follower = round_players[(idx + 1) % len(round_players)]
        return self._estimate_threshold(follower, stats)

    def _aggressive_threshold(self, round_players: list[str], stats) -> float:
        try:
            idx = round_players.index(self.name)
        except ValueError:
            return self.BASE_THRESHOLD
        follower_idx = (idx + 1) % len(round_players)
        others = [p for i, p in enumerate(round_players) if i != idx and i != follower_idx]
        if not others:
            return self.BASE_THRESHOLD
        return max(self._estimate_threshold(p, stats) for p in others)

    def _pick_target(self, round_players: list[str], stats) -> str | None:
        """Return the player most likely to challenge (highest known challenge_rate)."""
        if stats is None or not stats.challenge_rate:
            return None
        others = [p for p in round_players if p != self.name]
        known = [p for p in others if p in stats.challenge_rate]
        if not known:
            return None
        return max(known, key=lambda p: stats.challenge_rate[p])

    def _target_window(self, round_players: list[str], stats) -> tuple[float, float]:
        """(floor, ceiling) probabilities for a targeted pressure bid.

        floor: max challenge threshold of players who act between Shark and target
               (they must pass the bid as-is)
        ceiling: target's challenge threshold (they call after the next raise)
        Falls back to follower / aggressive thresholds when no target is identifiable.
        """
        target = self._pick_target(round_players, stats)
        if target is None:
            return (
                self._follower_threshold(round_players, stats),
                self._aggressive_threshold(round_players, stats),
            )
        try:
            my_idx = round_players.index(self.name)
            target_idx = round_players.index(target)
        except ValueError:
            return (
                self._follower_threshold(round_players, stats),
                self._aggressive_threshold(round_players, stats),
            )
        n = len(round_players)
        between = []
        i = (my_idx + 1) % n
        while i != target_idx:
            between.append(round_players[i])
            i = (i + 1) % n
        ceiling = self._estimate_threshold(target, stats)
        floor = max((self._estimate_threshold(p, stats) for p in between), default=0.0)
        return floor, ceiling

    def _pressure_bid(
        self,
        hand: list[int],
        prior_bet: Bet | None,
        total_dice: int,
        round_players: list[str],
        stats,
    ) -> Bet | None:
        floor, ceiling = self._target_window(round_players, stats)

        faces = sorted(
            range(2, 7),
            key=lambda f: hand.count(f) + hand.count(1),
            reverse=True,
        )

        for face in faces:
            if prior_bet is not None:
                if face < prior_bet.face:
                    continue
                min_qty = prior_bet.quantity + 1 if face == prior_bet.face else prior_bet.quantity
            else:
                min_qty = 1

            for q in range(total_dice, min_qty - 1, -1):
                p_self = self._prob_bet_holds(hand, face, q, total_dice)
                p_after = self._prob_bet_holds(hand, face, q + 1, total_dice)
                if p_self > floor and p_after < ceiling:
                    return Bet(q, face, self.name)

        return None

    def _call_threshold(self, prior_bet: Bet | None, stats) -> float:
        """Challenge threshold calibrated to the bidder's bluff rate, desperation,
        face-reveal frequency, and current round velocity."""
        base = self.BASE_CALL_THRESHOLD
        if prior_bet is None or stats is None:
            return base

        bluff_rate = stats.bluff_rate.get(prior_bet.player, 0.5)
        bluff_adj = (bluff_rate - 0.5) * self.BLUFF_SENSITIVITY

        dice = getattr(stats, "dice_counts", {}).get(prior_bet.player)
        desperation = (5 - dice) * self.DICE_DESPERATION_BOOST if dice is not None else 0.0

        # Raise threshold when bidder rarely shows this face in revealed hands (suspicious)
        face_adj = 0.0
        rounds_with = getattr(stats, "rounds_with_hand", {}).get(prior_bet.player, 0)
        if rounds_with >= 2:
            freq = getattr(stats, "revealed_hand_frequency", {}).get(prior_bet.player, {})
            if prior_bet.face != 1:
                observed = freq.get(prior_bet.face, 0.0) + freq.get(1, 0.0)
                expected = 2 / 6
            else:
                observed = freq.get(1, 0.0)
                expected = 1 / 6
            raw_bias = (observed - expected) * self.FACE_REVEAL_SENSITIVITY
            face_adj = -max(-0.08, min(0.08, raw_bias))

        # Lower threshold when round is escalating fast (backed bids); raise when slow (forced bluffing)
        velocity = getattr(stats, "current_round_velocity", 1.0)
        vel_adj = max(-0.10, min(0.10, -(velocity - 1.0) * self.VELOCITY_SENSITIVITY))

        return max(0.10, min(0.40, base + bluff_adj + desperation + face_adj + vel_adj))

    def _mean_held_penalty(self, face: int, stats) -> float:
        if stats is None:
            return 0.0
        mhq = stats.mean_held_quantity_by_face
        values = [mhq[p].get(face, 0.0) for p in mhq if p != self.name and face in mhq[p]]
        if not values:
            return 0.0
        return (sum(values) / len(values)) * self.MEAN_HELD_WEIGHT

    def _best_raise(self, hand: list[int], prior_bet: Bet, total_dice: int, stats) -> Bet:
        """Score every legal raise by own support, face-bias penalty, and hold probability.

        When holding 2+ of the bid face and the +2 jump still clears AGGRESSIVE_JUMP_FLOOR,
        take the jump immediately to pressure opponents into skipping a level.
        """
        own = hand.count(prior_bet.face) + (hand.count(1) if prior_bet.face != 1 else 0)
        if own >= 2:
            p2 = self._prob_bet_holds(hand, prior_bet.face, prior_bet.quantity + 2, total_dice)
            if p2 >= self.AGGRESSIVE_JUMP_FLOOR:
                return Bet(prior_bet.quantity + 2, prior_bet.face, self.name)

        candidates = []
        penalty = self._mean_held_penalty(prior_bet.face, stats)
        p1 = self._prob_bet_holds(hand, prior_bet.face, prior_bet.quantity + 1, total_dice)
        candidates.append(
            (prior_bet.quantity + 1, prior_bet.face, own - penalty + p1 * self.RAISE_PROB_WEIGHT)
        )
        for face in range(prior_bet.face + 1, 7):
            own_f = hand.count(face) + hand.count(1)
            penalty_f = self._mean_held_penalty(face, stats)
            p_holds = self._prob_bet_holds(hand, face, prior_bet.quantity, total_dice)
            candidates.append(
                (prior_bet.quantity, face, own_f - penalty_f + p_holds * self.RAISE_PROB_WEIGHT)
            )
        best = max(candidates, key=lambda c: c[2])
        return Bet(best[0], best[1], self.name)

    def _opening_factor(self, round_players: list[str], stats, base: float | None = None) -> float:
        """Opening aggression factor, adjusted for table challenge rate."""
        if base is None:
            base = self.BASE_OPENING_FACTOR
        if stats is None or not stats.challenge_rate:
            return base
        others = [p for p in round_players if p != self.name]
        if not others:
            return base
        avg_cr = sum(stats.challenge_rate.get(p, 0.20) for p in others) / len(others)
        adj = (self.OPENING_CR_PIVOT - avg_cr) * self.OPENING_CR_SENSITIVITY
        return max(self.OPENING_FACTOR_MIN, min(self.OPENING_FACTOR_MAX, base + adj))

    def algo(self, ctx: GameContext) -> Bet | None:
        hand = ctx.hand
        prior_bet = ctx.prior_bet
        total_dice = ctx.total_dice
        stats = ctx.stats
        round_players = ctx.round_players

        if len(round_players) > self.ATTRITION_THRESHOLD:
            return self._algo_attrition(hand, prior_bet, total_dice, round_players, stats)
        return self._algo_sniper(hand, prior_bet, total_dice, round_players, stats)

    def _algo_attrition(self, hand, prior_bet, total_dice, round_players, stats) -> Bet | None:
        if prior_bet is None:
            bid = self._pressure_bid(hand, None, total_dice, round_players, stats)
            factor = self._opening_factor(round_players, stats, self.ATTRITION_OPENING_BASE)
            return bid if bid is not None else self._solid_opening(hand, total_dice, factor)

        if self._prob_bet_holds(
            hand, prior_bet.face, prior_bet.quantity, total_dice
        ) < self._call_threshold(prior_bet, stats):
            return None

        bid = self._pressure_bid(hand, prior_bet, total_dice, round_players, stats)
        return bid if bid is not None else self._best_raise(hand, prior_bet, total_dice, stats)

    def _algo_sniper(self, hand, prior_bet, total_dice, round_players, stats) -> Bet | None:
        if prior_bet is None:
            factor = self._opening_factor(round_players, stats)
            return self._solid_opening(hand, total_dice, factor)

        if self._prob_bet_holds(
            hand, prior_bet.face, prior_bet.quantity, total_dice
        ) < self._call_threshold(prior_bet, stats):
            return None

        return self._best_raise(hand, prior_bet, total_dice, stats)

    def _solid_opening(self, hand: list[int], total_dice: int, factor: float) -> Bet:
        unseen = total_dice - len(hand)
        wildcards = hand.count(1)

        # Open on wildcards precisely when holding 2+ — no randomness, just backing
        if wildcards >= 2:
            qty = max(1, round(wildcards + unseen * (1 / 6) * factor))
            return Bet(qty, 1, self.name)

        best_face = max(range(2, 7), key=lambda f: hand.count(f) + wildcards)
        own = hand.count(best_face) + wildcards
        qty = max(1, round(own + unseen * (2 / 6) * factor))
        return Bet(qty, best_face, self.name)
