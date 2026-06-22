from math import comb

from game.components.bets import Bet
from game.components.context import GameContext


class Shark:
    name = "The Shark"

    # ── Tunable parameters ───────────────────────────────────────────────────

    BASE_THRESHOLD = 0.28        # fallback follower threshold (no stats)
    CR_INTERCEPT = 0.15          # threshold = CR_INTERCEPT + challenge_rate * CR_SLOPE
    CR_SLOPE = 0.65
    BASE_SNIPER_THRESHOLD = 0.28
    BLUFF_SENSITIVITY = 0.40
    BASE_OPENING_FACTOR = 0.80
    OPENING_CR_PIVOT = 0.22
    OPENING_CR_SENSITIVITY = 1.5
    OPENING_FACTOR_MIN = 0.55
    OPENING_FACTOR_MAX = 1.05
    MEAN_HELD_WEIGHT = 1.0
    ATTRITION_THRESHOLD = 3      # use attrition mode when player count > this

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
            comb(unseen, k) * (p**k) * ((1 - p) ** (unseen - k))
            for k in range(need, unseen + 1)
        )

    def _estimate_threshold(self, player: str, stats) -> float:
        cr = stats.challenge_rate.get(player) if stats is not None else None
        if cr is None:
            return self.BASE_THRESHOLD
        return max(0.15, min(0.45, self.CR_INTERCEPT + cr * self.CR_SLOPE))

    def algo(self, ctx: GameContext) -> Bet | None:
        raise NotImplementedError
