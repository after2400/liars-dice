from math import comb

from game.components.bets import Bet


class Diego:
    """
    Probability-driven strategy. Computes the exact binomial probability that
    the current bet holds given own hand, then calls liar when that probability
    drops below a threshold. Bids by anchoring to the face with the highest
    expected total count.
    """

    CALL_THRESHOLD = 0.30  # call liar when P(bet holds) < 30%

    name = "Diego"

    def _prob_bet_holds(self, hand: list, face: int, quantity: int, total_dice: int) -> float:
        """Probability that at least `quantity` dice show `face` across all dice.

        Uses own hand as known information; models each unseen die as independently
        showing the face with probability p (1/6 for face==1, 2/6 otherwise with wilds).
        """
        own = hand.count(face) + (hand.count(1) if face != 1 else 0)
        unseen = total_dice - len(hand)
        p = 1 / 6 if face == 1 else 2 / 6  # wild 1s count for non-1 faces

        need = quantity - own  # how many unseen dice must show face
        if need <= 0:
            return 1.0
        if need > unseen:
            return 0.0

        # P(X >= need) where X ~ Binomial(unseen, p)
        return sum(
            comb(unseen, k) * (p**k) * ((1 - p) ** (unseen - k)) for k in range(need, unseen + 1)
        )

    def algo(
        self,
        hand: list,
        prior_bet: Bet | None,
        total_dice: int,
        bet_history: list[dict],
        outcomes: list[dict],
    ) -> Bet | None:

        if prior_bet is None:
            # Open on the face with the highest expected total count
            best_face = max(range(2, 7), key=lambda f: hand.count(f) + hand.count(1))
            own = hand.count(best_face) + hand.count(1)
            unseen = total_dice - len(hand)
            expected_others = unseen * (2 / 6)
            quantity = max(1, round(own + expected_others * 0.7))  # conservative opening
            return Bet(quantity, best_face, self.name)

        # Evaluate probability the current bet holds
        p_holds = self._prob_bet_holds(hand, prior_bet.face, prior_bet.quantity, total_dice)
        if p_holds < self.CALL_THRESHOLD:
            return None  # call liar

        # Raise: find the best face to raise on
        own_on_face = hand.count(prior_bet.face) + (hand.count(1) if prior_bet.face != 1 else 0)

        if own_on_face > 0:
            # Raise quantity on same face - we have backing
            return Bet(prior_bet.quantity + 1, prior_bet.face, self.name)

        # Shift to a higher face we hold
        for face in range(prior_bet.face + 1, 7):
            if hand.count(face) + hand.count(1) > 0:
                return Bet(prior_bet.quantity, face, self.name)

        # Last resort: minimal raise on same face
        return Bet(prior_bet.quantity + 1, prior_bet.face, self.name)
