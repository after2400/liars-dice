from game.components.bets import Bet
from game.components.context import GameContext


class Topper:
    """
    Mechanical escalator. Topper always raises the prior bid by the smallest
    legal step in (quantity, face) order over faces 2-6: bump the face by one,
    and once the face is 6, increment the quantity and reset the face to 2.
    He only calls liar when that step would require more dice than are in play.

    Opens (no prior bet) at the ceiling: (total_dice // 3) sixes - a break-even
    bid (with wilds on, the expected count of any face is total_dice / 3).
    """

    name = "Topper"

    @staticmethod
    def _step(prior_bet: Bet) -> tuple[int, int]:
        """The next bid up from prior_bet as (quantity, face)."""
        if prior_bet.face < 6:
            return prior_bet.quantity, prior_bet.face + 1
        return prior_bet.quantity + 1, 2

    def algo(self, ctx: GameContext) -> Bet | None:
        prior_bet = ctx.prior_bet
        total_dice = ctx.total_dice
        if prior_bet is None:
            return Bet(max(1, total_dice // 3), 6, self.name)

        quantity, face = self._step(prior_bet)
        if quantity > total_dice:
            # The step needs more dice than exist - there's nothing higher to claim.
            return None
        return Bet(quantity, face, self.name)
