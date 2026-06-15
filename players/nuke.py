import random
from math import comb

from game.components.bets import Bet


class Nuke:
    """
    "Nuke LaLoosh" — raw talent, gut instinct. Opens on 1s ~75% of the time
    (his fastball), turning wilds off for the round. Stubbornly stays on 1s
    as long as the bid still has a pulse (P >= FASTBALL_HOLD_THRESHOLD).
    Calls liar only when his own counter-bid would be indefensible — he'd
    rather keep pitching than admit the count is off. Throws +2 when the
    numbers back it, +1 otherwise.
    """

    name = "Nuke LaLoosh"

    FASTBALL_PROB = 0.50  # probability of opening on 1s
    FASTBALL_HOLD_THRESHOLD = 0.40  # stay on 1s while P(current 1s bet) >= this
    BLUFF_CALL_THRESHOLD = 0.15  # call liar immediately when P(prior bet) < this
    RAISE_TWO_THRESHOLD = 0.40  # go +2 if P(quantity+2, face) >= this

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

    def _own_bid_threshold(self, total_dice: int) -> float:
        """Adaptive liar threshold: tolerant early (many dice), aggressive late (few dice)."""
        return min(0.40, 0.15 + 0.25 * (total_dice / 20.0))

    def _raise_amount(
        self, hand: list[int], face: int, current_quantity: int, total_dice: int
    ) -> int:
        """Return +2 if that bid is defensible, else +1."""
        if (
            self._prob_bet_holds(hand, face, current_quantity + 2, total_dice)
            >= self.RAISE_TWO_THRESHOLD
        ):
            return 2
        return 1

    def _fastball_eligible(self, hand: list[int], total_dice: int, outcomes: list[dict]) -> bool:
        """True when Nuke holds 1s and the game is in endgame (few players left)."""
        if not hand.count(1):
            return False
        # Infer starting pool from first round's hands; fall back to total_dice / 5
        if outcomes:
            n_start = len(outcomes[0].get("hands", {}))
            n_current = len(outcomes[-1].get("hands", {}))
        else:
            n_start = max(2, round(total_dice / 5))
            n_current = n_start
        threshold = 3 if n_start > 5 else 2
        return n_current <= threshold

    _OPENING_MULTIPLIER = {
        "L1": 0.85,  # aggressive — weaker field
        "CH": 0.82,  # calibrated — proven best in CH
        "PRM": 0.78,  # conservative — elite field
    }

    def algo(
        self,
        hand: list[int],
        prior_bet: Bet | None,
        total_dice: int,
        bet_history: list[dict],
        outcomes: list[dict],
        tier: str | None = None,
    ) -> Bet | None:
        if prior_bet is None:
            if random.random() < self.FASTBALL_PROB and self._fastball_eligible(
                hand, total_dice, outcomes
            ):
                own_1s = hand.count(1)
                unseen = total_dice - len(hand)
                quantity = max(own_1s + 1, round(own_1s + unseen * (1 / 6) * 0.7))
                return Bet(quantity, 1, self.name)
            multiplier = self._OPENING_MULTIPLIER.get(tier, 0.82) if tier else 0.82
            best_face = max(range(2, 7), key=lambda f: hand.count(f) + hand.count(1))
            own = hand.count(best_face) + hand.count(1)
            unseen = total_dice - len(hand)
            quantity = max(1, round(own + unseen * (2 / 6) * multiplier))
            return Bet(quantity, best_face, self.name)

        # Call liar immediately on an implausible prior bet
        if (
            self._prob_bet_holds(hand, prior_bet.face, prior_bet.quantity, total_dice)
            < self.BLUFF_CALL_THRESHOLD
        ):
            return None

        # Stubbornness on 1s: keep the wild-suppression pressure on while the bet looks credible
        if (
            prior_bet.face == 1
            and self._prob_bet_holds(hand, 1, prior_bet.quantity, total_dice)
            >= self.FASTBALL_HOLD_THRESHOLD
        ):
            amount = self._raise_amount(hand, 1, prior_bet.quantity, total_dice)
            candidate = Bet(prior_bet.quantity + amount, 1, self.name)
        # Backed on the current face: raise it (1s only if we personally hold them)
        elif hand.count(prior_bet.face) + (hand.count(1) if prior_bet.face != 1 else 0) > 0:
            amount = self._raise_amount(hand, prior_bet.face, prior_bet.quantity, total_dice)
            candidate = Bet(prior_bet.quantity + amount, prior_bet.face, self.name)
        else:
            candidate = None
            for face in range(prior_bet.face + 1, 7):
                if hand.count(face) + hand.count(1) > 0:
                    candidate = Bet(prior_bet.quantity, face, self.name)
                    break
            if candidate is None:
                # Last resort: raise quantity on same face
                amount = self._raise_amount(hand, prior_bet.face, prior_bet.quantity, total_dice)
                candidate = Bet(prior_bet.quantity + amount, prior_bet.face, self.name)

        # Only pitch if our own bid is defensible; otherwise admit the count is off
        if self._prob_bet_holds(
            hand, candidate.face, candidate.quantity, total_dice
        ) >= self._own_bid_threshold(total_dice):
            return candidate
        return None
