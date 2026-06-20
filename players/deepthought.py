from math import comb

from game.components.bets import Bet

DESPERATE_DICE = 2  # bidder counts as "desperate" at this many dice or fewer


class DeepThought:
    """
    The original Deep Thought took seven and a half million years to compute
    the Answer to Life, the Universe, and Everything, and the answer turned
    out to be useless without knowing the Question. This Deep Thought is
    faster and more useful: it just watches how many dice you had left the
    last time you bid. Bluff with five dice in hand and it shrugs. Bluff with
    two and it remembers — you, specifically, by name — and starts pricing
    in exactly how much you panic when cornered. Forty-two was never the
    answer. Mostly it's the player to your left who bids big right before
    they lose their last die.
    """

    name = "Deep Thought"

    # Call liar whenever P(bet holds) drops below this. Same base as Peter Beter.
    BASE_THRESHOLD = 0.22

    # How much of the unseen dice's expected count to claim when opening.
    OPENING_MULTIPLIER = 0.70

    # Weight given to our own raise's hold probability in candidate scoring.
    # Same as Peter Beter — validated separately, untouched here.
    RAISE_PROB_WEIGHT = 6.0

    # How strongly a bidder's desperation-conditioned bluff rate shifts the
    # call threshold for their bids specifically. Swept 0.15-0.4 against the
    # real PRM field (incl. Peter Beter); 0.3 was the peak, and the whole
    # range cleared the noise floor by 8-10x its own standard error.
    DESPERATION_SENSITIVITY = 0.3

    def __init__(self) -> None:
        self._bh_idx = 0
        self._oc_idx = 0
        self._round_key: tuple[int, int] | None = None
        self._game_key: int | None = None
        self._wilds_active = True
        self._last_bid_dice: dict[tuple[int, int], tuple[str, int]] = {}
        # name -> [bluffs, holds], tracked separately for desperate vs comfortable bids
        self._desperate: dict[str, list[int]] = {}
        self._comfortable: dict[str, list[int]] = {}

    def _sync(self, bet_history: list[dict], outcomes: list[dict]) -> None:
        n = len(bet_history)
        for i in range(self._bh_idx, n):
            entry = bet_history[i]
            if entry["game"] != self._game_key:
                self._game_key = entry["game"]
            round_key = (entry["game"], entry["round"])
            if round_key != self._round_key:
                self._round_key = round_key
                self._wilds_active = entry["bet"].face != 1
            self._last_bid_dice[round_key] = (entry["player"], entry["dice_count"])
        self._bh_idx = n

        m = len(outcomes)
        for j in range(self._oc_idx, m):
            outcome = outcomes[j]
            round_key = (outcome["game"], outcome["round"])
            last = self._last_bid_dice.get(round_key)
            if last is None or last[0] != outcome["bidder"]:
                continue
            bidder, dice_count = last
            bucket = self._desperate if dice_count <= DESPERATE_DICE else self._comfortable
            counts = bucket.setdefault(bidder, [0, 0])  # [bluffs, holds]
            if outcome["bet_held"]:
                counts[1] += 1
            else:
                counts[0] += 1
        self._oc_idx = m

    def _conditional_bluff_rate(self, bidder: str, desperate: bool) -> float | None:
        bucket = self._desperate if desperate else self._comfortable
        counts = bucket.get(bidder)
        if counts is None:
            return None
        bluffs, holds = counts
        return (bluffs + 1) / (bluffs + holds + 2)

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

    def _effective_threshold(self, prior_bet: Bet) -> float:
        """
        The bidder's own dice count at the moment of THIS bid (recorded in
        bet_history but otherwise unused league-wide) tells us how much they
        had to lose. Their bluff rate when desperate vs. comfortable can
        differ a lot — using the rate that actually matches their current
        situation is a better-calibrated estimate than blending all their
        history together.
        """
        last = self._last_bid_dice.get(self._round_key)
        if last is None or last[0] != prior_bet.player:
            return self.BASE_THRESHOLD
        bidder, dice_count = last
        desperate = dice_count <= DESPERATE_DICE
        rate = self._conditional_bluff_rate(bidder, desperate)
        if rate is None:
            return self.BASE_THRESHOLD
        adj = (rate - 0.5) * self.DESPERATION_SENSITIVITY
        return max(0.10, min(0.35, self.BASE_THRESHOLD + adj))

    def _best_raise(
        self, hand: list[int], prior_bet: Bet, total_dice: int, stats
    ) -> tuple[int, int]:
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
        self._sync(bet_history, outcomes)

        if prior_bet is None:
            self._wilds_active = True
            best_face = max(range(2, 7), key=lambda f: hand.count(f) + hand.count(1))
            own = hand.count(best_face) + hand.count(1)
            unseen = total_dice - len(hand)
            quantity = max(1, round(own + unseen * (2 / 6) * self.OPENING_MULTIPLIER))
            return Bet(quantity, best_face, self.name)

        threshold = self._effective_threshold(prior_bet)
        if self._prob_holds(prior_bet.face, prior_bet.quantity, hand, total_dice) < threshold:
            return None

        quantity, face = self._best_raise(hand, prior_bet, total_dice, stats)
        return Bet(quantity, face, self.name)
