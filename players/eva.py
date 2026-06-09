from math import comb

from game.components.bets import Bet


class Eva:
    """
    Opponent-calibrated strategy. Computes exact binomial probability like Diego,
    but adjusts the liar threshold per opponent based on their historical reliability.
    Known bluffers trigger calls earlier; reliable players get more benefit of the doubt.
    """

    name = "Eva"

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

    def _reliability(self, player_name: str, outcomes: list) -> float:
        held = sum(1 for o in outcomes if o["bidder"] == player_name and o["bet_held"])
        failed = sum(1 for o in outcomes if o["bidder"] == player_name and not o["bet_held"])
        total = held + failed
        return held / total if total > 0 else 0.5

    def _threshold(self, reliability: float) -> float:
        return 0.30 - (reliability - 0.5) * 0.30

    def algo(
        self,
        hand: list,
        prior_bet: Bet | None,
        total_dice: int,
        bet_history: list[dict],
        outcomes: list[dict],
    ) -> Bet | None:
        if prior_bet is None:
            best_face = max(range(2, 7), key=lambda f: hand.count(f) + hand.count(1))
            own = hand.count(best_face) + hand.count(1)
            unseen = total_dice - len(hand)
            quantity = max(
                1, round(own + unseen * (2 / 6) * 0.8)
            )  # slightly more aggressive than Diego's 0.7
            return Bet(quantity, best_face, self.name)

        reliability = self._reliability(prior_bet.player, outcomes)
        threshold = self._threshold(reliability)

        if self._prob_bet_holds(hand, prior_bet.face, prior_bet.quantity, total_dice) < threshold:
            return None

        own = hand.count(prior_bet.face) + (hand.count(1) if prior_bet.face != 1 else 0)
        if own > 0:
            return Bet(prior_bet.quantity + 1, prior_bet.face, self.name)
        for face in range(prior_bet.face + 1, 7):
            if hand.count(face) + hand.count(1) > 0:
                return Bet(prior_bet.quantity, face, self.name)
        return Bet(prior_bet.quantity + 1, prior_bet.face, self.name)
