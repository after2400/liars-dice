import random
from math import comb

from game.components.bets import Bet


class Rick:
    """
    Wubba lubba dub dub. Rick Sanchez is the smartest man in the universe and
    he wants you to know it. He opens with aggressive wild-dice bluffs because
    he's already run the probability calculation in his head (and in four parallel
    dimensions). He calls liar early and often — mostly out of contempt — and
    occasionally goes completely off-script just to prove he can. Don't question
    it, Morty.

    Strategy:
    - Opens aggressively on 1s (wilds) whenever he has any — classic Rick flex.
    - Calls liar at a low probability threshold; he assumes everyone else is bluffing.
    - Has a 15% chance of making a totally unhinged raise (quantity + 2 or +3) to
      assert dominance. Science.
    - Tracks opponents' bluff history because he's literally a genius.
    """

    name = "Rick Sanchez"

    # Rick calls liar the moment P(bet holds) drops below this — low because he
    # assumes everyone around him is an idiot and/or bluffing.
    CALL_THRESHOLD = 0.28

    # Fraction of time Rick opens with a 1s (wild dice) bid — his signature move.
    WILD_OPEN_PROB = 0.70

    # Fraction of time Rick randomly escalates by +2 or +3 instead of +1 just
    # to assert intellectual dominance and unsettle the table.
    CHAOS_RAISE_PROB = 0.15

    def __init__(self) -> None:
        self._opp: dict[str, dict] = {}
        self._last_outcomes_len: int = 0

    def _ingest(self, outcomes: list[dict]) -> None:
        for o in outcomes[self._last_outcomes_len :]:
            if "bidder" not in o:
                continue
            bidder = o["bidder"]
            d = self._opp.setdefault(bidder, {"bluffs": 0, "holds": 0})
            if o["bet_held"]:
                d["holds"] += 1
            else:
                d["bluffs"] += 1
        self._last_outcomes_len = len(outcomes)

    def _bluff_rate(self, bidder: str) -> float:
        d = self._opp.get(bidder)
        if d is None:
            return 0.5  # unknown — assume average idiot
        b, h = d["bluffs"], d["holds"]
        return (b + 1) / (b + h + 2)

    def _prob_holds(self, hand: list[int], face: int, quantity: int, total_dice: int) -> float:
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
        tier: str | None = None,
    ) -> Bet | None:
        self._ingest(outcomes)

        if prior_bet is None:
            # Open on 1s (wilds) when Rick has any — the statistically optimal
            # aggressive opener, and also it looks cool.
            if random.random() < self.WILD_OPEN_PROB and hand.count(1) > 0:
                own_1s = hand.count(1)
                unseen = total_dice - len(hand)
                # Slightly generous estimate — Rick is confident, not delusional.
                quantity = max(own_1s + 1, round(own_1s + unseen * (1 / 6) * 0.9))
                return Bet(quantity, 1, self.name)

            # Fallback: best non-wild face, opened aggressively.
            best_face = max(range(2, 7), key=lambda f: hand.count(f) + hand.count(1))
            own = hand.count(best_face) + hand.count(1)
            unseen = total_dice - len(hand)
            quantity = max(1, round(own + unseen * (2 / 6) * 1.0))
            return Bet(quantity, best_face, self.name)

        # Adjust call threshold based on how much of an idiot the bidder is.
        bluff_adj = (self._bluff_rate(prior_bet.player) - 0.5) * 0.2
        threshold = max(0.10, self.CALL_THRESHOLD + bluff_adj)

        p = self._prob_holds(hand, prior_bet.face, prior_bet.quantity, total_dice)
        if p < threshold:
            # "I've run the math, Morty. They're lying."
            return None

        # Rick raises. Occasionally goes unhinged for psychological effect.
        bump = random.choice([2, 3]) if random.random() < self.CHAOS_RAISE_PROB else 1

        own_on_face = hand.count(prior_bet.face) + (hand.count(1) if prior_bet.face != 1 else 0)
        if own_on_face > 0:
            return Bet(prior_bet.quantity + bump, prior_bet.face, self.name)

        # No dice on that face — shift to a higher one.
        for face in range(prior_bet.face + 1, 7):
            if hand.count(face) + hand.count(1) > 0:
                return Bet(prior_bet.quantity, face, self.name)

        # Last resort: raw raise. Morty would panic here. Rick does not.
        return Bet(prior_bet.quantity + bump, prior_bet.face, self.name)
