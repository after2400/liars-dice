from math import comb

from game.components.bets import Bet
from game.components.context import GameContext


class Finn:
    """
    Game-state adaptive strategy. Computes exact binomial probability like Diego,
    but scales the liar threshold with total dice remaining. With many dice the
    threshold peaks at 0.40 (Finn tolerates more uncertainty early); as dice thin
    out it drops to ~0.21 (Finn demands stronger evidence before calling liar late,
    entering end-game with fewer die losses). Raises by 2 when well-backed (own >= 2)
    to apply extra pressure.
    """

    name = "Finn"
    avatar = "hdyiihba/Finn_Carter.png"

    def _prob_bet_holds(self, hand: list, face: int, quantity: int, total_dice: int) -> float:
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

    def _threshold(self, total_dice: int) -> float:
        return min(0.40, 0.15 + 0.25 * (total_dice / 20.0))

    def algo(self, ctx: GameContext) -> Bet | None:
        hand = ctx.hand
        prior_bet = ctx.prior_bet
        total_dice = ctx.total_dice
        if prior_bet is None:
            best_face = max(range(2, 7), key=lambda f: hand.count(f) + hand.count(1))
            own = hand.count(best_face) + hand.count(1)
            unseen = total_dice - len(hand)
            quantity = max(
                1, round(own + unseen * (2 / 6) * 0.75)
            )  # between Diego's 0.7 and Eva's 0.8
            return Bet(quantity, best_face, self.name)

        own = hand.count(prior_bet.face) + (hand.count(1) if prior_bet.face != 1 else 0)

        if self._prob_bet_holds(
            hand, prior_bet.face, prior_bet.quantity, total_dice
        ) < self._threshold(total_dice):
            return None
        if own >= 2:
            return Bet(prior_bet.quantity + 2, prior_bet.face, self.name)
        if own > 0:
            return Bet(prior_bet.quantity + 1, prior_bet.face, self.name)
        for face in range(prior_bet.face + 1, 7):
            if hand.count(face) + hand.count(1) > 0:
                return Bet(prior_bet.quantity, face, self.name)
        return Bet(prior_bet.quantity + 1, prior_bet.face, self.name)
