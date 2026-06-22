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
        others = [
            p for i, p in enumerate(round_players)
            if i != idx and i != follower_idx
        ]
        if not others:
            return self.BASE_THRESHOLD
        return max(self._estimate_threshold(p, stats) for p in others)

    def _pressure_bid(
        self,
        hand: list[int],
        prior_bet: Bet | None,
        total_dice: int,
        round_players: list[str],
        stats,
    ) -> Bet | None:
        follower_thr = self._follower_threshold(round_players, stats)
        aggressive_thr = self._aggressive_threshold(round_players, stats)

        # Faces 2-6 sorted by own support (best first); skip 1s in attrition mode
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

            # Search from ceiling down to min_qty
            for q in range(total_dice, min_qty - 1, -1):
                p_self = self._prob_bet_holds(hand, face, q, total_dice)
                p_after = self._prob_bet_holds(hand, face, q + 1, total_dice)
                if p_self > follower_thr and p_after < aggressive_thr:
                    return Bet(q, face, self.name)

        return None

    def _sniper_threshold(self, prior_bet: Bet | None, stats) -> float:
        if prior_bet is None or stats is None:
            return self.BASE_SNIPER_THRESHOLD
        bluff_rate = stats.bluff_rate.get(prior_bet.player, 0.5)
        adj = (bluff_rate - 0.5) * self.BLUFF_SENSITIVITY
        return max(0.15, min(0.45, self.BASE_SNIPER_THRESHOLD + adj))

    def _mean_held_penalty(self, face: int, stats) -> float:
        if stats is None:
            return 0.0
        mhq = stats.mean_held_quantity_by_face
        values = [mhq[p].get(face, 0.0) for p in mhq if p != self.name and face in mhq[p]]
        if not values:
            return 0.0
        return (sum(values) / len(values)) * self.MEAN_HELD_WEIGHT

    def _sniper_raise(self, hand: list[int], prior_bet: Bet, total_dice: int, stats) -> Bet:
        candidates = []
        # Same face, quantity+1
        own = hand.count(prior_bet.face) + (hand.count(1) if prior_bet.face != 1 else 0)
        penalty = self._mean_held_penalty(prior_bet.face, stats)
        candidates.append((prior_bet.quantity + 1, prior_bet.face, own - penalty))
        # Higher faces, same quantity
        for face in range(prior_bet.face + 1, 7):
            own = hand.count(face) + hand.count(1)
            penalty = self._mean_held_penalty(face, stats)
            candidates.append((prior_bet.quantity, face, own - penalty))
        best = max(candidates, key=lambda c: c[2])
        return Bet(best[0], best[1], self.name)

    def _sniper_opening_factor(self, round_players: list[str], stats) -> float:
        if stats is None or not stats.challenge_rate:
            return self.BASE_OPENING_FACTOR
        others = [p for p in round_players if p != self.name]
        if not others:
            return self.BASE_OPENING_FACTOR
        avg_cr = sum(stats.challenge_rate.get(p, 0.20) for p in others) / len(others)
        adj = (self.OPENING_CR_PIVOT - avg_cr) * self.OPENING_CR_SENSITIVITY
        return max(self.OPENING_FACTOR_MIN, min(self.OPENING_FACTOR_MAX, self.BASE_OPENING_FACTOR + adj))

    def algo(self, ctx: GameContext) -> Bet | None:
        raise NotImplementedError
