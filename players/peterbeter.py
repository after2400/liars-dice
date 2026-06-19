from math import comb

from game.components.bets import Bet


class PeterBeter:
    """
    There is, scientifically, only one purpose for this bot: dominate Peter
    Griffin. Not Stewie, not Cal, not the rest of the league — Peter, by
    name, on purpose, with a clipboard and a grudge. Turns out Peter's one
    blind spot was never checking whether HIS OWN raise was actually any
    good — he'd raise whatever looked best to the guy across the table and
    just hope it held. Peter Beter does that math too. Freakin' sweet doesn't
    cut it when your opponent's literally also named Peter and also doing
    math now. Roadhouse.
    """

    name = "Peter Beter"

    # Call liar whenever P(bet holds) drops below this. Same as Peter Griffin.
    CALL_THRESHOLD = 0.22

    # How much of the unseen dice's expected count to claim when opening.
    OPENING_MULTIPLIER = 0.70

    # Weight given to our own raise's hold probability in candidate scoring.
    # Validated head-to-head against weight 3.0 and a hard safety filter —
    # 6.0 came out ahead of both by a margin that cleared the noise floor.
    RAISE_PROB_WEIGHT = 6.0

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

    def _support(self, hand: list[int], face: int) -> int:
        wb = self._wild_bonus(face)
        return hand.count(face) + (hand.count(1) if wb else 0)

    def _prob_holds(self, face: int, quantity: int, hand: list[int], total_dice: int) -> float:
        own = self._support(hand, face)
        need = quantity - own
        if need <= 0:
            return 1.0
        unseen = total_dice - len(hand)
        if need > unseen:
            return 0.0
        p = 2 / 6 if self._wild_bonus(face) else 1 / 6
        return sum(
            comb(unseen, k) * (p**k) * ((1 - p) ** (unseen - k)) for k in range(need, unseen + 1)
        )

    def _face_bias(self, face: int, stats) -> float:
        if stats is None or not stats.face_bias:
            return 1 / 6
        biases = [pb.get(face, 1 / 6) for pb in stats.face_bias.values()]
        return sum(biases) / len(biases)

    def _best_raise(
        self, hand: list[int], prior_bet: Bet, total_dice: int, stats
    ) -> tuple[int, int]:
        """
        Score every viable raise at once — same face +1 included — instead of
        always defaulting to it. Candidates are ranked by how much support we
        hold, how strongly opponents already lean toward that face (a face
        they avoid is harder to disbelieve), AND — the piece Peter Griffin
        never checked — how likely the resulting bet is to actually survive a
        challenge. Looking good to opponents and being true aren't the same
        thing; only one of them used to matter here.
        """
        candidates = []

        own_on_bid_face = self._support(hand, prior_bet.face)
        if own_on_bid_face > 0:
            bias = self._face_bias(prior_bet.face, stats)
            candidates.append((prior_bet.quantity + 1, prior_bet.face, own_on_bid_face, bias))

        for face in range(prior_bet.face + 1, 7):
            own = self._support(hand, face)
            if own > 0:
                bias = self._face_bias(face, stats)
                candidates.append((prior_bet.quantity, face, own, bias))

        if not candidates:
            return prior_bet.quantity + 1, prior_bet.face

        best = max(
            candidates,
            key=lambda c: (
                c[2] * 2.0
                - c[3] * 3.0
                + self._prob_holds(c[1], c[0], hand, total_dice) * self.RAISE_PROB_WEIGHT
            ),
        )
        return best[0], best[1]

    def algo(
        self,
        hand: list[int],
        prior_bet: Bet | None,
        total_dice: int,
        bet_history: list[dict],
        outcomes: list[dict],
        stats=None,
    ) -> Bet | None:
        self._sync_wilds(bet_history)

        if prior_bet is None:
            self._wilds_active = True
            best_face = max(range(2, 7), key=lambda f: hand.count(f) + hand.count(1))
            own = hand.count(best_face) + hand.count(1)
            unseen = total_dice - len(hand)
            quantity = max(1, round(own + unseen * (2 / 6) * self.OPENING_MULTIPLIER))
            return Bet(quantity, best_face, self.name)

        if (
            self._prob_holds(prior_bet.face, prior_bet.quantity, hand, total_dice)
            < self.CALL_THRESHOLD
        ):
            return None

        quantity, face = self._best_raise(hand, prior_bet, total_dice, stats)
        return Bet(quantity, face, self.name)
