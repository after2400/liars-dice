import random

from game.components.bets import Bet


class Cleo:
    """
    Mood-driven strategy. Each turn randomly adopts an aggressive or cautious
    stance, then makes logically grounded decisions within that frame.

    Aggressive: bluffs above expected counts, calls liar only on clear overreach.
    Cautious: bids conservatively, calls liar at the first sign of excess.
    """

    name = "Cleo"

    def _estimate(self, hand: list, face: int, total_dice: int) -> float:
        """Expected total count of `face` across all dice, using own hand + probability."""
        own = hand.count(face) + (hand.count(1) if face != 1 else 0)
        unseen = total_dice - len(hand)
        # Each unseen die shows face ~1/6, plus wilds (~1/6) for non-1 faces
        expected_others = unseen * (2 / 6 if face != 1 else 1 / 6)
        return own + expected_others

    def algo(
        self,
        hand: list,
        prior_bet: Bet | None,
        total_dice: int,
        bet_history: list[dict],
        outcomes: list[dict],
    ) -> Bet | None:
        aggressive = random.random() < 0.5

        if prior_bet is None:
            best_face = max(range(2, 7), key=lambda f: hand.count(f) + hand.count(1))
            estimated = self._estimate(hand, best_face, total_dice)
            if aggressive:
                # Bluff above expected — open high to pressure opponents
                quantity = int(estimated) + random.randint(1, 2)
            else:
                # Open conservatively at or just below own estimate
                quantity = max(1, int(estimated) - random.randint(0, 1))
            return Bet(quantity, best_face, self.name)

        estimated = self._estimate(hand, prior_bet.face, total_dice)

        # Decide whether to call liar based on how far the bet exceeds our estimate
        liar_threshold = 1.4 if aggressive else 1.0
        if prior_bet.quantity > estimated * liar_threshold:
            return None

        # Raise: aggressive takes big quantity leaps, cautious prefers face raises
        if aggressive:
            quantity = prior_bet.quantity + random.randint(2, 3)
            face = prior_bet.face
        else:
            if prior_bet.face < 6:
                return Bet(prior_bet.quantity, prior_bet.face + 1, self.name)
            quantity = prior_bet.quantity + 1
            face = 2

        return Bet(quantity, face, self.name)
