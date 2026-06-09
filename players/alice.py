import logging

from game.components.bets import Bet

logger = logging.getLogger(__name__)


class Alice:
    """
    Balanced strategy. Uses hand to anchor bids and calls liar when the
    running bet exceeds ~1.25x the statistically expected count.
    """

    name = "Alice"

    def algo(
        self,
        hand: list,
        prior_bet: Bet | None,
        total_dice: int,
        bet_history: list[dict],
        outcomes: list[dict],
    ) -> Bet | None:
        # Expected count of any non-1 face across all dice (1s are wild, so ~1/3 chance per die)
        expected = total_dice / 3

        if prior_bet is None:
            # Open with the face we hold most of (wilds included)
            best_face = max(range(2, 7), key=lambda f: hand.count(f) + hand.count(1))
            count = hand.count(best_face) + hand.count(1)
            return Bet(max(1, count), best_face, self.name)

        # Call liar if bet is well above expected
        if prior_bet.quantity > expected * 1.25:
            return None

        # Raise on same face if we hold any matching dice
        own = hand.count(prior_bet.face) + (hand.count(1) if prior_bet.face != 1 else 0)
        if own > 0:
            return Bet(prior_bet.quantity + 1, prior_bet.face, self.name)

        # Shift to a higher face we actually hold
        for face in range(prior_bet.face + 1, 7):
            if hand.count(face) + hand.count(1) > 0:
                return Bet(prior_bet.quantity, face, self.name)

        # No good option - raise quantity or bail
        if prior_bet.quantity + 1 > expected * 2:
            return None
        return Bet(prior_bet.quantity + 1, prior_bet.face, self.name)
