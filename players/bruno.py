from game.components.bets import Bet


class Bruno:
    """
    Aggressive strategy. Opens at own count, raises by 1 when holding the face,
    shifts to a higher held face when not, and calls liar above 1.5x expected.
    """

    name = "Bruno"

    def algo(
        self,
        hand: list,
        prior_bet: Bet | None,
        total_dice: int,
        bet_history: list[dict],
        outcomes: list[dict],
    ) -> Bet | None:
        expected = total_dice / 3

        if prior_bet is None:
            best_face = max(range(2, 7), key=lambda f: hand.count(f) + hand.count(1))
            count = hand.count(best_face) + hand.count(1)
            return Bet(max(1, count), best_face, self.name)

        if prior_bet.quantity > expected * 1.5:
            return None

        own = hand.count(prior_bet.face) + (hand.count(1) if prior_bet.face != 1 else 0)
        if own > 0:
            return Bet(prior_bet.quantity + 1, prior_bet.face, self.name)

        # Shift to a higher face we hold rather than raising blind
        for face in range(prior_bet.face + 1, 7):
            if hand.count(face) + hand.count(1) > 0:
                return Bet(prior_bet.quantity, face, self.name)

        return Bet(prior_bet.quantity + 1, prior_bet.face, self.name)
