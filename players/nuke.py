import random
from math import comb

from game.components.bets import Bet


class Nuke:
    name = "Nuke LaLoosh"

    BASE_CALL_THRESHOLD = 0.28
    CALL_FLOOR = 0.10
    STEWIE_CALL_FLOOR = 0.12
    BLUFF_SENSITIVITY = 0.40
    VELOCITY_SENSITIVITY = 0.015

    FASTBALL_PROB = 0.50

    RAISE_OWN_WEIGHT = 2.0
    RAISE_BIAS_PENALTY = 3.0
    ENDGAME_THRESHOLD = 5

    OPENING_FACTOR_DEFAULT = 0.82
    OPENING_CR_PIVOT = 0.25
    OPENING_CR_SENSITIVITY = 1.5
    OPENING_FACTOR_MIN = 0.55
    OPENING_FACTOR_MAX = 1.0

    def _crash_davis_called_pitch(self, bidder: str, face: int, stats) -> float:
        floor = self.STEWIE_CALL_FLOOR if bidder == "Stewie" else self.CALL_FLOOR
        if stats is None:
            return max(floor, self.BASE_CALL_THRESHOLD)
        face_bluff = stats.bluff_rate_by_face.get(bidder, {}).get(face)
        overall_bluff = stats.bluff_rate.get(bidder)
        if face_bluff is not None and overall_bluff is not None:
            bluff_signal = face_bluff * 0.3 + overall_bluff * 0.7
        elif overall_bluff is not None:
            bluff_signal = overall_bluff
        else:
            bluff_signal = 0.5
        bluff_adj = (bluff_signal - 0.5) * self.BLUFF_SENSITIVITY
        velocity_adj = max(0.0, stats.current_round_velocity - 1.0) * self.VELOCITY_SENSITIVITY
        raw = self.BASE_CALL_THRESHOLD + bluff_adj - velocity_adj
        return max(floor, min(0.50, raw))

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

    def _own_fraction(self, hand: list[int], face: int, total_dice: int, wilds: bool) -> float:
        if total_dice == 0:
            return 0.0
        count = hand.count(face)
        if wilds and face != 1:
            count += hand.count(1)
        return count / total_dice

    def _avg_opp_face_bias(self, face: int, stats) -> float:
        if stats is None or not stats.face_bias:
            return 1 / 6
        biases = [pb.get(face, 1 / 6) for pb in stats.face_bias.values()]
        return sum(biases) / len(biases)

    def _best_raise(
        self, hand: list[int], prior_bet: Bet, total_dice: int, stats
    ) -> tuple[int, int]:
        wilds = prior_bet.face != 1
        endgame = total_dice <= self.ENDGAME_THRESHOLD
        candidates = []
        frac = self._own_fraction(hand, prior_bet.face, total_dice, wilds)
        bias = 0.0 if endgame else self._avg_opp_face_bias(prior_bet.face, stats)
        candidates.append((prior_bet.quantity + 1, prior_bet.face, frac, bias))
        for face in range(prior_bet.face + 1, 7):
            frac = self._own_fraction(hand, face, total_dice, wilds)
            bias = 0.0 if endgame else self._avg_opp_face_bias(face, stats)
            candidates.append((prior_bet.quantity, face, frac, bias))
        best = max(
            candidates,
            key=lambda c: c[2] * self.RAISE_OWN_WEIGHT - c[3] * self.RAISE_BIAS_PENALTY,
        )
        return best[0], best[1]

    def _opening_factor(self, stats) -> float:
        if stats is None or not stats.challenge_rate:
            return self.OPENING_FACTOR_DEFAULT
        avg_cr = sum(stats.challenge_rate.values()) / len(stats.challenge_rate)
        adjustment = (self.OPENING_CR_PIVOT - avg_cr) * self.OPENING_CR_SENSITIVITY
        return max(
            self.OPENING_FACTOR_MIN,
            min(self.OPENING_FACTOR_MAX, self.OPENING_FACTOR_DEFAULT + adjustment),
        )

    def _next_player(self, bet_history: list[dict]) -> str | None:
        for i in range(len(bet_history) - 1, 0, -1):
            prev, curr = bet_history[i - 1], bet_history[i]
            if prev["player"] == self.name and prev["round"] == curr["round"]:
                return curr["player"]
        return None

    def algo(
        self,
        hand: list[int],
        prior_bet: Bet | None,
        total_dice: int,
        bet_history: list[dict],
        outcomes: list[dict],
        stats=None,
        tier: str | None = None,
    ) -> Bet | None:
        if prior_bet is None:
            ones_count = hand.count(1)
            unseen = total_dice - len(hand)

            if tier == "PRM":
                if ones_count >= 2 and self._next_player(bet_history) == "Stewie":
                    qty = max(2, round(ones_count + unseen * (1 / 6) * 0.7))
                    return Bet(qty, 1, self.name)
            elif ones_count > 0 and random.random() < self.FASTBALL_PROB:
                qty = max(ones_count + 1, round(ones_count + unseen * (1 / 6) * 0.7))
                return Bet(qty, 1, self.name)

            factor = self._opening_factor(stats)
            best_face = max(range(2, 7), key=lambda f: hand.count(f) + ones_count)
            own = hand.count(best_face) + ones_count
            qty = max(1, round(own + unseen * (2 / 6) * factor))
            return Bet(qty, best_face, self.name)

        p_holds = self._prob_bet_holds(hand, prior_bet.face, prior_bet.quantity, total_dice)
        threshold = self._crash_davis_called_pitch(prior_bet.player, prior_bet.face, stats)
        if p_holds < threshold:
            return None

        qty, face = self._best_raise(hand, prior_bet, total_dice, stats)
        return Bet(qty, face, self.name)
