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

    Now also watches opening bids. When a player opens a round on face=5,
    that's not random — it correlates with what they're holding. Deep Thought
    remembers, infers, and adjusts accordingly. EvilStewie taught it this.
    """

    name = "Deep Thought"

    # Call liar whenever P(bet holds) drops below this. Same base as Peter Beter.
    BASE_THRESHOLD = 0.22

    # How much of the unseen dice's expected count to claim when opening.
    OPENING_MULTIPLIER = 0.70

    # Weight given to our own raise's hold probability in candidate scoring.
    RAISE_PROB_WEIGHT = 6.0

    # How strongly a bidder's desperation-conditioned bluff rate shifts the
    # call threshold for their bids specifically. Swept 0.15-0.4 against the
    # real PRM field (incl. Peter Beter); 0.3 was the peak.
    DESPERATION_SENSITIVITY = 0.3

    # Weight given to the bidder's face-specific bluff rate when blended with
    # the desperation-conditioned rate. Swept 0.15-0.6 at 750 paired trials;
    # 0.45 peaked at z=+4.61 vs control.
    FACE_WEIGHT = 0.45

    # Penalty multiplier applied to (1 - p_holds) of a raise, scaled by the
    # estimated next-player challenge rate. Discourages bidding into aggressive
    # challengers with weak support. No constant needed — uses challenge_rate
    # from stats directly.
    CALL_PENALTY_WEIGHT = 2.0

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

    def _round_opening_bids(
        self, bet_history: list[dict]
    ) -> dict[str, tuple[int, float, int]]:
        """Return {player: (face, effective_qty, dice_count)} for each other player's first bid this round.

        For the true opener (first bet of the round), full qty is credited as signal.
        For subsequent bidders, only the excess over the minimum raise + a face-commitment
        fraction is credited — they were constrained by the prior, so their signal is weaker.
        """
        if not bet_history or self._round_key is None:
            return {}
        entries: list[dict] = []
        for entry in reversed(bet_history):
            if (entry["game"], entry["round"]) != self._round_key:
                break
            entries.append(entry)
        entries.reverse()

        result: dict[str, tuple[int, float, int]] = {}
        for i, entry in enumerate(entries):
            p = entry["player"]
            if p == self.name or p in result:
                continue
            face = entry["bet"].face
            qty = entry["bet"].quantity
            d = entry["dice_count"]
            if i == 0:
                result[p] = (face, float(qty), d)
            else:
                prev = entries[i - 1]["bet"]
                if qty > prev.quantity:
                    min_qty, n_opts = prev.quantity + 1, 5
                else:
                    min_qty, n_opts = prev.quantity, 6 - prev.face
                effective_qty = max(0, qty - min_qty) + qty / n_opts
                result[p] = (face, effective_qty, d)
        return result

    def _infer_held(
        self,
        bid_face: int,
        bid_qty: float,
        d: int,
        total_dice: int,
        face: int,
        wilds: bool,
        bluff_rate: float = 0.0,
    ) -> tuple[int, int]:
        """Infer (certain_matches, uncertain_dice) for a player given their opening bid.

        Under rational no-bluffing, a player opens with:
            bid_qty ≈ own_matches + (total_dice - d) * p

        Inverting: own_matches ≈ bid_qty - (total_dice - d) * p

        bluff_rate discounts the inferred count: a known bluffer's signal is trusted
        proportionally less, shifting dice back into the uncertain pool.
        """
        if bid_face != face:
            return 0, d
        p = 1 / 6 if (face == 1 or not wilds) else 2 / 6
        expected_from_others = (total_dice - d) * p
        inferred = round(max(0.0, min(float(d), bid_qty - expected_from_others)))
        certain = round(inferred * (1.0 - bluff_rate))
        return certain, d - certain

    def _next_player(self, bet_history: list[dict]) -> str | None:
        """Infer who follows us in the current round from the bet sequence.

        Scans this round's bets in order, finds the last position where DT bet,
        and returns whoever bet right after. Returns None when DT hasn't bet yet
        this round (e.g. we're the first to respond).
        """
        if not bet_history or self._round_key is None:
            return None
        players_this_round: list[str] = []
        for entry in reversed(bet_history):
            if (entry["game"], entry["round"]) != self._round_key:
                break
            players_this_round.append(entry["player"])
        players_this_round.reverse()

        for i in range(len(players_this_round) - 1, -1, -1):
            if players_this_round[i] == self.name and i + 1 < len(players_this_round):
                return players_this_round[i + 1]
        return None

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

    def _prob_holds(
        self,
        face: int,
        quantity: int,
        hand: list[int],
        total_dice: int,
        opening_bids: dict[str, tuple[int, float, int]] | None = None,
        bluff_rates: dict[str, float] | None = None,
    ) -> float:
        """P(bid holds), optionally incorporating opponent opening-bid inference.

        When opening_bids is provided, unseen dice are partitioned into:
          certain  — inferred matching dice from rational opener analysis
          uncertain — remaining dice modeled as binomial at base rate p

        Without opening_bids, falls back to pure binomial over all unseen dice.
        """
        own = self._support(hand, face)
        wilds = self._wild_bonus(face)

        if opening_bids:
            certain = own
            accounted = sum(d for _, _, d in opening_bids.values())
            uncertain = total_dice - len(hand) - accounted
            for player, (bid_face, bid_qty, d) in opening_bids.items():
                br = (bluff_rates or {}).get(player, 0.0)
                c, u = self._infer_held(bid_face, bid_qty, d, total_dice, face, wilds, br)
                certain += c
                uncertain += u
        else:
            certain = own
            uncertain = total_dice - len(hand)

        p = 2 / 6 if wilds else 1 / 6
        need = quantity - certain
        if need <= 0:
            return 1.0
        if need > uncertain:
            return 0.0
        return sum(
            comb(uncertain, k) * (p**k) * ((1 - p) ** (uncertain - k))
            for k in range(need, uncertain + 1)
        )

    def _face_bias(self, face: int, stats) -> float:
        if stats is None or not stats.face_bias:
            return 1 / 6
        biases = [pb.get(face, 1 / 6) for pb in stats.face_bias.values()]
        return sum(biases) / len(biases)

    def _effective_threshold(self, prior_bet: Bet, stats) -> float:
        """
        The bidder's own dice count at the moment of THIS bid (recorded in
        bet_history but otherwise unused league-wide) tells us how much they
        had to lose. Their bluff rate when desperate vs. comfortable can
        differ a lot — using the rate that actually matches their current
        situation is a better-calibrated estimate than blending all their
        history together.

        Blended with stats.bluff_rate_by_face — the desperation signal is
        face-blind, but a bidder's bluff tendency on THIS specific face is
        independent evidence the engine already computes for free.
        """
        last = self._last_bid_dice.get(self._round_key)
        if last is None or last[0] != prior_bet.player:
            return self.BASE_THRESHOLD
        bidder, dice_count = last
        desperate = dice_count <= DESPERATE_DICE
        desp_rate = self._conditional_bluff_rate(bidder, desperate)

        face_rate = None
        if stats is not None:
            face_rate = stats.bluff_rate_by_face.get(bidder, {}).get(prior_bet.face)

        if desp_rate is None and face_rate is None:
            return self.BASE_THRESHOLD
        if desp_rate is None:
            rate = face_rate
        elif face_rate is None:
            rate = desp_rate
        else:
            rate = self.FACE_WEIGHT * face_rate + (1 - self.FACE_WEIGHT) * desp_rate

        adj = (rate - 0.5) * self.DESPERATION_SENSITIVITY
        return max(0.10, min(0.35, self.BASE_THRESHOLD + adj))

    def _best_raise(
        self,
        hand: list[int],
        prior_bet: Bet,
        total_dice: int,
        stats,
        opening_bids: dict[str, tuple[int, float, int]] | None = None,
        bluff_rates: dict[str, float] | None = None,
        p_call: float = 0.3,
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

        scored = []
        for qty, face, own, bias in candidates:
            ph = self._prob_holds(face, qty, hand, total_dice, opening_bids, bluff_rates)
            score = (
                own * 2.0
                - bias * 3.0
                + ph * self.RAISE_PROB_WEIGHT
                - p_call * (1.0 - ph) * self.CALL_PENALTY_WEIGHT
            )
            scored.append((score, qty, face))

        best = max(scored, key=lambda x: x[0])
        return best[1], best[2]

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

        # Compute opening bid inference and bluff rates once for this turn
        opening_bids = self._round_opening_bids(bet_history)
        bluff_rates = stats.bluff_rate if stats is not None else {}

        # Estimate next-player challenge rate for raise scoring
        next_p = self._next_player(bet_history)
        p_call = 0.3
        if stats is not None and next_p is not None:
            p_call = stats.challenge_rate.get(next_p, 0.3)

        threshold = self._effective_threshold(prior_bet, stats)
        if self._prob_holds(prior_bet.face, prior_bet.quantity, hand, total_dice, opening_bids, bluff_rates) < threshold:
            return None

        quantity, face = self._best_raise(hand, prior_bet, total_dice, stats, opening_bids, bluff_rates, p_call)
        return Bet(quantity, face, self.name)
