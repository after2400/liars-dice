from math import comb

from game.components.bets import Bet


class CalCulated:
    """
    Cal did the homework so you don't have to. He photocopied Diego's exact
    strategy (open conservative, flat threshold, raise whatever face you're
    not embarrassed by), then bolted on three "improvements" of his own —
    opponent bluff-rate tracking, round-momentum vibes, optimizing every raise
    like a man with a TI-84 and a grudge — and ran the numbers. All three
    were either dead weight or actively made him worse, so he deleted them
    and told everyone he "explored the design space." The only thing he
    actually invented: remembering that 1s stop being wild once someone bids
    on them, a fact every other bot in this league has apparently agreed to
    forget. Cal will never let you live that down.
    """

    name = "Cal Culatid"

    OPENING_MULTIPLIER = 0.70
    THRESHOLD = 0.30

    def __init__(self) -> None:
        self._bh_idx = 0
        self._round_key: tuple[int, int] | None = None
        self._wilds_active = True

    def _sync_wilds(self, bet_history: list[dict]) -> None:
        for i in range(self._bh_idx, len(bet_history)):
            entry = bet_history[i]
            key = (entry["game"], entry["round"])
            if key != self._round_key:
                self._round_key = key
                self._wilds_active = entry["bet"].face != 1
        self._bh_idx = len(bet_history)

    def _wild_bonus(self, face: int) -> bool:
        return self._wilds_active and face != 1

    def _prob_holds(self, face: int, quantity: int, hand: list[int], total_dice: int) -> float:
        wild_bonus = self._wild_bonus(face)
        own = hand.count(face) + (hand.count(1) if wild_bonus else 0)
        need = quantity - own
        if need <= 0:
            return 1.0
        unseen = total_dice - len(hand)
        if need > unseen:
            return 0.0
        p = 2 / 6 if wild_bonus else 1 / 6
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
        self._sync_wilds(bet_history)

        if prior_bet is None:
            # We always open on a non-1 face, so wilds are on for this round
            # regardless of what last round left behind.
            self._wilds_active = True
            best_face = max(range(2, 7), key=lambda f: hand.count(f) + hand.count(1))
            own = hand.count(best_face) + hand.count(1)
            unseen = total_dice - len(hand)
            quantity = max(1, round(own + unseen * (2 / 6) * self.OPENING_MULTIPLIER))
            return Bet(quantity, best_face, self.name)

        if self._prob_holds(prior_bet.face, prior_bet.quantity, hand, total_dice) < self.THRESHOLD:
            return None

        wild_bonus = self._wild_bonus(prior_bet.face)
        own = hand.count(prior_bet.face) + (hand.count(1) if wild_bonus else 0)
        if own > 0:
            return Bet(prior_bet.quantity + 1, prior_bet.face, self.name)

        for face in range(prior_bet.face + 1, 7):
            wb = self._wild_bonus(face)
            if hand.count(face) + (hand.count(1) if wb else 0) > 0:
                return Bet(prior_bet.quantity, face, self.name)

        return Bet(prior_bet.quantity + 1, prior_bet.face, self.name)
