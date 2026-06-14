import random
from math import comb

from game.components.bets import Bet


class Nuke:
    """
    "Nuke LaLoosh" — raw talent, zero discipline. Opens on 1s ~75% of the time
    (his fastball), turning wilds off for the round and disrupting everyone's
    expected counts. Occasionally throws a changeup (best non-1 face, Diego-style).

    Liar-calling uses Diego's exact binomial but with CALL_THRESHOLD tuned for
    Nuke's personality. Raises by RAISE_WHEN_BACKED when he has backing.
    """

    name = "Nuke LaLoosh"

    FASTBALL_PROB = 0.75  # probability of opening on 1s
    CALL_THRESHOLD = 0.20  # call liar when P(bet holds) < this
    RAISE_WHEN_BACKED = 1  # quantity raise when holding the prior face

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
            comb(unseen, k) * (p**k) * ((1 - p) ** (unseen - k)) for k in range(need, unseen + 1)
        )

    def algo(
        self,
        hand: list[int],
        prior_bet: Bet | None,
        total_dice: int,
        bet_history: list[dict],
        outcomes: list[dict],
    ) -> Bet | None:
        if prior_bet is None:
            if random.random() < self.FASTBALL_PROB:
                own_1s = hand.count(1)
                unseen = total_dice - len(hand)
                # Always claims at least one more than he holds — never backs down
                quantity = max(own_1s + 1, round(own_1s + unseen * (1 / 6) * 0.7))
                return Bet(quantity, 1, self.name)
            best_face = max(range(2, 7), key=lambda f: hand.count(f) + hand.count(1))
            own = hand.count(best_face) + hand.count(1)
            unseen = total_dice - len(hand)
            quantity = max(1, round(own + unseen * (2 / 6) * 0.7))
            return Bet(quantity, best_face, self.name)

        if (
            self._prob_bet_holds(hand, prior_bet.face, prior_bet.quantity, total_dice)
            < self.CALL_THRESHOLD
        ):
            return None

        own_on_face = hand.count(prior_bet.face) + (hand.count(1) if prior_bet.face != 1 else 0)
        if own_on_face > 0:
            return Bet(prior_bet.quantity + self.RAISE_WHEN_BACKED, prior_bet.face, self.name)

        for face in range(prior_bet.face + 1, 7):
            if hand.count(face) + hand.count(1) > 0:
                return Bet(prior_bet.quantity, face, self.name)

        return Bet(prior_bet.quantity + 1, prior_bet.face, self.name)
