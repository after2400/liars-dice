from math import comb

from game.components.bets import Bet
from game.components.context import GameContext

DESPERATE_DICE = 2  # bidder counts as "desperate" at this many dice or fewer


class DeepThought:
    """
    The original Deep Thought took seven and a half million years to compute
    the Answer to Life, the Universe, and Everything. This one is faster and
    actually useful in a bar argument.

    Three layered signals feed the call threshold: (1) desperation-conditioned
    bluff rate — panicked (≤2 dice) vs comfortable bids are tracked separately,
    because panic-bluffing is a distinct tell; (2) face-specific bluff rate from
    the engine, blended at FACE_WEIGHT=0.45; (3) round velocity — fast escalation
    signals overextension.

    Opening bids use inference from each player's first bet to partition unseen
    dice into "likely matches" and "uncertain" pools (EvilStewie's approach). The
    opening factor scales with table aggression — passive tables absorb higher
    opens. Raises score own support, face bias, hold probability, and a penalty
    for the next player's challenge rate (exact, from ctx.round_players v2).
    """

    name = "Deep Thought"

    # Call liar whenever P(bet holds) drops below this. Empirically confirmed
    # optimal at 0.22 vs the PRM field; raising to 0.28+ costs 2-6pp — both
    # Stewie and EvilStewie's bids are genuinely well-supported.
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

    # Penalty applied to (1 - p_holds) of a raise, scaled by the next-player
    # challenge rate. Discourages bidding into aggressive challengers with weak
    # support. Validated: z=+3.07, +1.74pp in the real PRM field.
    CALL_PENALTY_WEIGHT = 2.0

    # How much each unit of round velocity above 1.0 tightens the call threshold.
    # Velocity = avg quantity increment per bid this round; fast escalation signals
    # overextension. Mirrors Stewie's validated approach.
    VELOCITY_SENSITIVITY = 0.02

    # Pivot and sensitivity for the adaptive opening factor. The opening factor
    # scales how much of the expected-others count to claim when opening a round.
    # Passive tables (low avg challenge rate) → open higher; aggressive → lower.
    OPENING_CR_PIVOT = 0.22
    OPENING_CR_SENSITIVITY = 2.0
    OPENING_FACTOR_MIN = 0.50
    OPENING_FACTOR_MAX = 1.10

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

    def _sync(self, ctx: GameContext) -> None:
        bet_history = ctx.bet_history
        outcomes = ctx.outcomes

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

    def _round_opening_bids(self, bet_history) -> dict[str, tuple[int, float, int]]:
        """Return {player: (face, effective_qty, dice_count)} for each other player's first bid this round.

        For the true opener (first bet of the round), full qty is credited as signal.
        For subsequent bidders, only the excess over the minimum raise + a face-commitment
        fraction is credited — they were constrained by the prior, so their signal is weaker.
        """
        if not bet_history or self._round_key is None:
            return {}
        entries = []
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

    def _next_player(self, ctx: GameContext) -> str | None:
        """Return who acts immediately after Deep Thought this round.

        Uses ctx.round_players (exact v2 ordering) — no inference needed.
        """
        players = ctx.round_players
        if not players:
            return None
        try:
            idx = players.index(self.name)
        except ValueError:
            return None
        return players[(idx + 1) % len(players)]

    def _conditional_bluff_rate(self, bidder: str, desperate: bool) -> float | None:
        bucket = self._desperate if desperate else self._comfortable
        counts = bucket.get(bidder)
        if counts is None:
            return None
        bluffs, holds = counts
        return (bluffs + 1) / (bluffs + holds + 2)

    def _opening_factor(self, stats) -> float:
        """Scale opening bid aggressiveness by table's average challenge rate.

        Passive tables (avg CR < pivot) tolerate higher opens; aggressive tables
        punish them. Mirrors Stewie's validated dynamic opening logic.
        """
        if not stats.challenge_rate:
            return self.OPENING_MULTIPLIER
        avg_cr = sum(stats.challenge_rate.values()) / len(stats.challenge_rate)
        adj = (self.OPENING_CR_PIVOT - avg_cr) * self.OPENING_CR_SENSITIVITY
        return max(
            self.OPENING_FACTOR_MIN,
            min(self.OPENING_FACTOR_MAX, self.OPENING_MULTIPLIER + adj),
        )

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
        if not stats.face_bias:
            return 1 / 6
        biases = [pb.get(face, 1 / 6) for pb in stats.face_bias.values()]
        return sum(biases) / len(biases)

    def _effective_threshold(self, prior_bet: Bet, stats) -> float:
        """
        Blends three signals into one call threshold:

        1. Desperation-conditioned bluff rate — bidder's bluff rate segmented by
           whether they were desperate (≤2 dice) at bid time. Panic-bluffing and
           comfortable-bluffing are different behaviors worth tracking separately.

        2. Face-specific bluff rate — per-face evidence from the engine, blended
           with the desperation signal at FACE_WEIGHT=0.45.

        3. Round velocity — fast escalation signals overextension. Each unit above
           1.0 tightens the threshold by VELOCITY_SENSITIVITY=0.02.
        """
        velocity = stats.current_round_velocity
        velocity_adj = max(0.0, velocity - 1.0) * self.VELOCITY_SENSITIVITY

        last = self._last_bid_dice.get(self._round_key)
        if last is None or last[0] != prior_bet.player:
            return max(0.10, min(0.40, self.BASE_THRESHOLD + velocity_adj))
        bidder, dice_count = last
        desperate = dice_count <= DESPERATE_DICE
        desp_rate = self._conditional_bluff_rate(bidder, desperate)
        face_rate = stats.bluff_rate_by_face.get(bidder, {}).get(prior_bet.face)

        if desp_rate is None and face_rate is None:
            return max(0.10, min(0.40, self.BASE_THRESHOLD + velocity_adj))
        if desp_rate is None:
            rate = face_rate
        elif face_rate is None:
            rate = desp_rate
        else:
            rate = self.FACE_WEIGHT * face_rate + (1 - self.FACE_WEIGHT) * desp_rate

        adj = (rate - 0.5) * self.DESPERATION_SENSITIVITY
        return max(0.10, min(0.40, self.BASE_THRESHOLD + adj + velocity_adj))

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

    def algo(self, ctx: GameContext) -> Bet | None:
        self._sync(ctx)

        hand = ctx.hand
        prior_bet = ctx.prior_bet
        total_dice = ctx.total_dice
        stats = ctx.stats

        if prior_bet is None:
            self._wilds_active = True
            best_face = max(range(2, 7), key=lambda f: hand.count(f) + hand.count(1))
            own = hand.count(best_face) + hand.count(1)
            unseen = total_dice - len(hand)
            factor = self._opening_factor(stats)
            quantity = max(1, round(own + unseen * (2 / 6) * factor))
            return Bet(quantity, best_face, self.name)

        # Opening bid inference and bluff rates for this turn
        opening_bids = self._round_opening_bids(ctx.bet_history)
        bluff_rates = stats.bluff_rate

        # Exact next-player from v2 round_players — no inference needed
        next_p = self._next_player(ctx)
        p_call = stats.challenge_rate.get(next_p, 0.3) if next_p else 0.3

        threshold = self._effective_threshold(prior_bet, stats)
        if (
            self._prob_holds(
                prior_bet.face, prior_bet.quantity, hand, total_dice, opening_bids, bluff_rates
            )
            < threshold
        ):
            return None

        quantity, face = self._best_raise(
            hand, prior_bet, total_dice, stats, opening_bids, bluff_rates, p_call
        )
        return Bet(quantity, face, self.name)
