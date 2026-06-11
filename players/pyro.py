from game.components.bets import Bet


class Pyro:
    """
    "Liar², Pants on Fire" - plays exactly like Topper, raising the prior bid by
    the smallest legal step in (quantity, face) order over faces 2-6, but with a
    shorter fuse: she calls liar as soon as that step's quantity would exceed
    1/3 of the dice in play (e.g. 4x6 with 12 dice steps to 5x2, and 5 > 12/3,
    so she calls liar).

    Opens (no prior bet) with (total_dice // 3) fives - the same break-even
    quantity as Topper, but one face below his sixes so she keeps a rung of
    face-stepping headroom.
    """

    name = "Liar², Pants on Fire"

    @staticmethod
    def _step(prior_bet: Bet) -> tuple[int, int]:
        """The next bid up from prior_bet as (quantity, face)."""
        if prior_bet.face < 6:
            return prior_bet.quantity, prior_bet.face + 1
        return prior_bet.quantity + 1, 2

    def algo(
        self,
        hand: list,
        prior_bet: Bet | None,
        total_dice: int,
        bet_history: list[dict],
        outcomes: list[dict],
    ) -> Bet | None:
        if prior_bet is None:
            return Bet(max(1, total_dice // 3), 5, self.name)

        quantity, face = self._step(prior_bet)
        if quantity > total_dice / 3:
            # Stepping past a third of the dice is too rich for her - call liar.
            return None
        return Bet(quantity, face, self.name)
