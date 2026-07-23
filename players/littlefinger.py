from __future__ import annotations

from math import comb

from game.components.bets import Bet
from game.components.context import GameContext


class Littlefinger:
    """
    Chaos is a ladder — and every rung is audited.

    The table runs on secondhand information: they invert your bids into
    "certain" dice, they fit the tripwire on your call button, they keep
    ledgers on who bluffs and when. Littlefinger read their ledgers first.

    He plays the bleed race, all the way down — no endgame switch, because
    the whole game is the endgame. Bids are priced under per-opponent call
    curves fitted from revealed hands, refit per stack size; their raises are
    read back at them as support floors on their hands. The call door prices
    each bidder's realized honesty, so squeezers get called on reputation.
    And when two bids price within a whisper, he takes the one his hand least
    supports — their certain-dice ledger banks a die he does not have.

    He never needed to lie about the dice. He lied in their data.
    """

    name = "Littlefinger"

    # --- Opponent call model: replicate their EV calc ---
    POP_BASE_RATE = 0.3  # challenge-rate prior for unseen players
    # Outcomes reveal every hand, so every past call/pass is re-scored with
    # the decider's exact private hold-prob. Closed-form tau early; a joint
    # (tau, slope) MLE takes over with labels, plus five per-stack-size tau
    # buckets at the pooled slope (their threshold drifts with stack size).
    TAU_PRIOR = 0.3
    TAU_SLOPE = 0.05
    TAU_MIN_OBS_CALLS = 3
    TAU_MIN_OBS_PASSES = 10
    TAU_FIT_MIN = 40  # labels before the first fit
    TAU_FIT_EVERY = 25  # new labels between refits
    TAU_FIT_CAP = 400  # labels kept per player

    # --- Survival policy ---
    CALL_MARGIN = 0.15  # call liar only when strictly cheaper than the safest raise
    OPEN_CAP_DIV = 2  # opening search: quantities up to total//DIV + 1
    BAIT_WEIGHT = 0.5  # credit for a called-and-held bid (the caller bleeds)
    SQUEEZE_WEIGHT = 0.3  # prefer bids that corner the next player

    # --- Poison policy ---
    # Among bids within EPS of optimal loss, take the one our hand least
    # supports: their certain-dice inference banks a die we do not have.
    # Below MIN_DICE we play honest — short stacks get believed.
    POISON_EPS = 0.05
    POISON_MIN_DICE = 3

    # --- Honesty thermostat (reputation closed loop, levers off) ---
    # A marginal bid of ours (our-seat hold-prob in the band) is either
    # called or raised over; the realized called-rate is the observable
    # proxy for how honest they think we are. temp low (read honest): widen
    # the poison band, squeeze more. temp high (well poisoned): band to its
    # floor, bait up. The edge is the harvest — lie when cheap so they keep
    # calling our honest bids; the setpoint self-limits.
    HON_TEMP = 0  # lever: thermostat-driven poison band
    HON_TEMP_W = 0  # lever: thermostat-driven bait/squeeze lerp
    TEMP_P_LO = 0.15  # marginal band on our bid's hold-prob
    TEMP_P_HI = 0.45
    TEMP_MIN_OBS = 15  # marginal resolutions before actuating
    TEMP_TARGET = 0.33  # called-rate setpoint (= Beta(2,4) prior mean)
    TEMP_K = 0.25  # eps gain per unit of temp error
    TEMP_LO = 0.02  # band floor
    TEMP_HI = 0.12  # band ceiling
    TEMP_WK = 1.5  # weight lerp gain
    # Per-judge temps: only the next live player clockwise can ever call our
    # bid, so reputation is per left-neighbor, shrunk toward the global pool.
    TEMP_PER_OPP = 0  # lever: per-judge posteriors
    TEMP_OPP_SHRINK = 10.0
    # Priced dose: within the poison band, take the bid minimizing the
    # judge-priced loss (sting, bait, squeeze against the actual next
    # player's call curve, not the all-players aggregate). Off; the
    # min-support pick runs instead.
    POISON_EV = 0

    # --- Call-door personalization (their honesty, read back) ---
    # CALL_FIT: per-bidder honesty curve P(hold | judge-seat p) fitted on
    # revealed hands — every opponent bid in every completed round is a
    # label. Honest bidders select into supported bids (realized hold rate
    # above the uniform price); bluffers sit below it. Blended with uniform
    # by label count.
    # CALL_SUP_W: asymmetric squeeze read — their support posterior may
    # LOWER P(their bid holds) (a same-qty 6-raise is the weakest honesty
    # class) but never lift it above the uniform price.
    CALL_FIT = 1
    CALL_FIT_SHRINK = 40.0  # uniform pseudo-labels blended into each curve
    CALL_SUP_W = 0.5  # 0 = uniform call door

    # --- Support-posterior bid pricing (the raise-door delta model) ---
    # Per-opponent per-face ABSOLUTE support estimates, reset each round, fed
    # by raise-class-weighted evidence (measured on revealed hands):
    #   qty raise to f:  support +0.95 over uniform  -> w 1.0 (the classic)
    #   same-qty to f<6: support +0.87, skipped -0.3 -> w 0.9 + anti-support
    #   same-qty to 6:   support +0.36, skipped -0.15, f0 +0.1 (the squeeze)
    # Raw posteriors over-price the door (winner's curse on the argmax face),
    # so deviations shrink by SHRINK. Used ONLY in the raise door.
    SUP_W_QTY = 1.0
    SUP_W_FLO = 0.9
    SUP_W_F6 = 0.35
    SUP_SKIP_FLO = 0.6  # anti-support per skipped face, same-qty to f<6
    SUP_SKIP_F6 = 0.3  # anti-support per skipped face, same-qty to 6
    SUP_UNDER_F6 = 0.2  # support under the bid (f0) after a same-qty 6-raise
    SUP_SHRINK = 0.5

    def __init__(self) -> None:
        # Per-opponent call/pass labels, re-scored with the decider's exact
        # private hold-prob (their hand is revealed in the outcome). Each
        # label also carries the decider's dice count for the bucketed fit.
        self._priv_call: dict[str, list[float]] = {}  # [sum, n]
        self._priv_pass: dict[str, list[float]] = {}
        self._labels: dict[str, list[tuple[float, bool, int]]] = {}
        self._fit: dict[str, tuple[float, float]] = {}  # player -> (tau, slope)
        self._fit_n: dict[str, int] = {}
        self._fit_d: dict[tuple[str, str], tuple[float, float]] = {}  # (player, bucket)
        self._fit_d_n: dict[tuple[str, str], int] = {}
        # Monotonic label counter (labels are front-trimmed at the cap, so
        # len() can't key caches) + last-scanned marker for _fit_dice.
        self._labels_total: dict[str, int] = {}
        self._fit_d_scan: dict[str, int] = {}
        self._seen_outcomes = 0
        self._seen_bets = 0
        # Support-belief state: player -> [0, est_1, .., est_6], reset per
        # round (hands re-roll): _held floors for their call curve, _sup
        # posteriors for our raise door. _supcache memoizes the convolutions.
        self._held: dict[str, list[float]] = {}
        self._held_key = None
        self._held_seen = 0  # bet_history index: entries folded into _held
        self._held_start = 0  # first bet_history index of the current round
        self._held_outcomes = 0  # outcomes count at last reset check
        self._sup: dict[str, list[float]] = {}
        self._supcache: dict[tuple, list[float]] = {}
        # Binomial survival memo: (n, p, k) -> exact P(X >= k). The tails are
        # the hot path (every call/hold price), and n <= 45 with p in
        # {1/6, 1/3} means a few thousand distinct values per series.
        self._bcache: dict[tuple[int, float, int], float] = {}
        # Honesty-thermostat state: FIFO of our unresolved bids (qty, face, p,
        # judge), resolved in _consume_round; Beta(2,4) posterior over the
        # marginal ones, global + per-judge.
        self._self_bids: list[tuple[int, int, float, str | None]] = []
        self._temp_a = 2.0
        self._temp_b = 4.0
        self._temp_obs = 0
        self._opp_a: dict[str, float] = {}
        self._opp_b: dict[str, float] = {}
        # Honesty-curve state: per-bidder (judge-seat p, failed) labels from
        # revealed hands, logistic fit blended into the call door.
        self._hon_labels: dict[str, list[tuple[float, bool]]] = {}
        self._hon_fit: dict[str, tuple[float, float]] = {}
        self._hon_fit_n: dict[str, int] = {}
        self._hon_total: dict[str, int] = {}
        self._hon_scan: dict[str, int] = {}

    def algo(self, ctx: GameContext) -> Bet | None:
        hand = ctx.hand
        prior = ctx.prior_bet
        total = ctx.total_dice
        wilds = ctx.stats.ones_are_wild if ctx.stats else True
        self._learn(ctx)
        self._update_held(ctx, hand, total)
        bet = self._survive(ctx, hand, prior, total, wilds)
        if self.HON_TEMP and bet is not None:
            p = self._p_bid_hold(ctx, bet.quantity, bet.face, hand, total, wilds)
            self._self_bids.append((bet.quantity, bet.face, p, self._judge(ctx)))
            if len(self._self_bids) > 200:  # defensive: drop ancient stales
                del self._self_bids[: len(self._self_bids) - 200]
        return bet

    # ── The bleed race ────────────────────────────────────────────────────────

    def _survive(self, ctx, hand, prior, total, wilds) -> Bet | None:
        """Minimize P(we lose a die this turn), priced as a dice differential.

        Raising costs us a die exactly when someone calls and the bid fails,
        but a called-and-held bid costs the CALLER a die — every opponent die
        loss brings the win closer:
            L_raise(b) = P_any_call(b) * (1 - p_hold(b))
                         - BAIT * P_any_call(b) * p_hold(b)
        Calling liar costs us a die exactly when the prior holds:
            L_call = p_hold(prior)
        Take the cheaper door. When no bid is safe, P_any_call -> 1 and the
        argmin collapses to the most statistically likely bid — the fallback.
        """
        if prior is None:
            best, _ = self._safest_bid(
                ctx, hand, 1, min(total, total // self.OPEN_CAP_DIV + 1), total, wilds, None
            )
            return best

        l_call = self._l_call(ctx, prior, hand, total, wilds)
        min_face = 1 if prior.face == 1 else 2  # never re-open 1s
        best_bid, best_loss = self._safest_bid(
            ctx, hand, prior.quantity, prior.quantity + 1, total, wilds, (prior, min_face)
        )
        if best_bid is None:
            return None  # bid is already (total, 6): calling is the only move
        if l_call < best_loss - self.CALL_MARGIN:
            return None
        return best_bid

    def _l_call(self, ctx, prior, hand, total, wilds) -> float:
        """Cost of calling liar: P(the prior bid holds), personalized.

        Uniform price from our seat, shrunk toward the bidder's realized
        honesty curve (CALL_FIT), then the asymmetric squeeze read: their
        support posterior may lower the price, never raise it (CALL_SUP_W).
        """
        cost = self._p_hold_faced(
            prior.player, self._p_holds(prior.quantity, prior.face, hand, total, wilds)
        )
        if self.CALL_SUP_W:
            p_sup = self._p_bid_hold(ctx, prior.quantity, prior.face, hand, total, wilds)
            cost = min(cost, (1.0 - self.CALL_SUP_W) * cost + self.CALL_SUP_W * p_sup)
        return cost

    def _p_hold_faced(self, bidder, q) -> float:
        """P(their bid holds): uniform price blended toward the bidder's
        realized hold curve as their label count grows."""
        if not self.CALL_FIT:
            return q
        self._fit_hon(bidder)
        fit = self._hon_fit.get(bidder)
        if fit is None:
            return q
        tau_h, s_h = fit
        p_fit = 1.0 - self._sig((tau_h - q) / s_h)
        n = self._hon_fit_n[bidder]
        w = n / (n + self.CALL_FIT_SHRINK)
        return (1.0 - w) * q + w * p_fit

    def _fit_hon(self, bidder) -> None:
        """Per-bidder (tau, slope) MLE over (judge-seat p, failed) labels."""
        labels = self._hon_labels.get(bidder)
        if not labels:
            return
        n = self._hon_total.get(bidder, 0)
        if self._hon_scan.get(bidder) == n:
            return
        self._hon_scan[bidder] = n
        if (
            len(labels) < self.TAU_FIT_MIN
            or n - self._hon_fit_n.get(bidder, 0) < self.TAU_FIT_EVERY
        ):
            return
        self._hon_fit[bidder] = self._mle(labels)
        self._hon_fit_n[bidder] = n

    def _safest_bid(self, ctx, hand, q_lo, q_hi, total, wilds, prior_info):
        """Argmin-loss legal bid over quantities [q_lo, q_hi].

        Among faces 2-6 the public hold-prob is identical (same wild math), so
        per quantity only our-seat hold-prob picks the face — except face 1,
        whose public math differs and which we never volunteer.
        """
        prior, min_face = prior_info if prior_info else (None, 1)
        best_bet, best_loss = None, float("inf")
        cand = []  # (loss, bet) for every legal bid — the near-tie pool
        pcall_cache = {}  # (qty, p_hit) -> P(any call): faces 2-6 share call math
        judge = self._judge(ctx)
        bait_w, squeeze_w = self._weights(judge)
        eps = self._poison_eps(judge)
        for qty in range(q_lo, q_hi + 1):
            faces = range(min_face, 7) if qty == (prior.quantity if prior else qty) else range(2, 7)
            for face in faces:
                if prior is not None and not (
                    qty > prior.quantity or (qty == prior.quantity and face > prior.face)
                ):
                    continue
                p_hold = self._p_bid_hold(ctx, qty, face, hand, total, wilds)
                ck = (qty, 2 / 6 if (wilds and face != 1) else 1 / 6)
                p_call = pcall_cache.get(ck)
                if p_call is None:
                    p_call = self._p_any_call(ctx, qty, face, total, wilds)
                    pcall_cache[ck] = p_call
                loss = p_call * (1.0 - p_hold) - bait_w * p_call * p_hold
                sq = 0.0
                if squeeze_w:
                    # A bid that passes but leaves the next player no cheap
                    # safe raise corners THEM into the bag-holding seat.
                    sq = 1.0 - self._best_reraise_pub(qty, face, total, wilds)
                    loss -= squeeze_w * sq * (1.0 - p_call)
                bet = Bet(qty, face, self.name)
                cand.append((loss, bet, p_hold, sq))
                if loss < best_loss - 1e-12:
                    best_bet, best_loss = bet, loss
        if eps > 0 and len(hand) >= self.POISON_MIN_DICE:
            # Every bid within EPS of optimal costs us the same in expectation,
            # but not to THEM: six of the eight infer our "certain" dice from
            # our first bid of the round (held ~= qty - unseen*p). Among the
            # interchangeable bids, take the one our hand least supports.
            band = [c for c in cand if c[0] <= best_loss + eps]
            if len(band) > 1 and self.POISON_EV and judge is not None:
                jcache = {}  # (qty, p_hit) -> P(the judge calls): faces 2-6 share math

                def jloss(c):
                    b = c[1]
                    ck = (b.quantity, 2 / 6 if (wilds and b.face != 1) else 1 / 6)
                    p_jc = jcache.get(ck)
                    if p_jc is None:
                        p_jc = self._p_call_struct(
                            ctx.stats, judge, b.quantity, b.face, total, wilds
                        )
                        jcache[ck] = p_jc
                    return (
                        p_jc * (1.0 - c[2]) - bait_w * p_jc * c[2] - squeeze_w * c[3] * (1.0 - p_jc)
                    )

                best_bet = min(band, key=lambda c: (jloss(c), c[0], (c[1].quantity, c[1].face)))[1]
            elif len(band) > 1:
                best_bet = min(
                    band,
                    key=lambda c: (
                        self._count(hand, c[1].face, wilds),
                        c[0],
                        (c[1].quantity, c[1].face),
                    ),
                )[1]
        return best_bet, best_loss

    def _temp(self) -> float:
        """Posterior mean of P(they call our marginal bid): the honesty temp."""
        return self._temp_a / (self._temp_a + self._temp_b)

    def _judge(self, ctx):
        """The only opponent who can call our next bid: next live player clockwise."""
        players = ctx.round_players
        if players and len(players) > 1 and self.name in players:
            return players[(players.index(self.name) + 1) % len(players)]
        return None

    def _temp_for(self, judge) -> float:
        """Effective temp for a judge: per-opp posterior shrunk to the global pool."""
        if not self.TEMP_PER_OPP or judge is None:
            return self._temp()
        a = self._opp_a.get(judge, 0.0)
        b = self._opp_b.get(judge, 0.0)
        return (a + self.TEMP_OPP_SHRINK * self._temp()) / (a + b + self.TEMP_OPP_SHRINK)

    def _poison_eps(self, judge=None) -> float:
        if not self.HON_TEMP or self._temp_obs < self.TEMP_MIN_OBS:
            return self.POISON_EPS
        eps = self.POISON_EPS + self.TEMP_K * (self.TEMP_TARGET - self._temp_for(judge))
        return min(self.TEMP_HI, max(self.TEMP_LO, eps))

    def _weights(self, judge=None) -> tuple[float, float]:
        if not self.HON_TEMP_W or self._temp_obs < self.TEMP_MIN_OBS:
            return self.BAIT_WEIGHT, self.SQUEEZE_WEIGHT
        err = self.TEMP_WK * (self._temp_for(judge) - self.TEMP_TARGET)
        bait = self.BAIT_WEIGHT * min(2.0, max(0.5, 1.0 + err))
        squeeze = self.SQUEEZE_WEIGHT * min(2.0, max(0.5, 1.0 - err))
        return bait, squeeze

    def _best_reraise_pub(self, qty, face, total, wilds) -> float:
        """Public hold-prob of the next player's best cheap raise over (qty, face)."""
        min_face = 2 if wilds else 1
        options = [self._p_holds_public(qty + 1, min_face, total, wilds)]
        if face < 6:
            options.append(self._p_holds_public(qty, face + 1, total, wilds))
        return max(options)

    # ── The call model: their EV calc, reconstructed ──────────────────────────

    def _learn(self, ctx) -> None:
        """Label every completed round: who let a bid pass, who called it.

        bet_history records every bet (called or not); outcomes record how
        the round resolved. For each bet after the opener, the bettor chose
        to raise rather than call — a pass at the prior bet's private
        hold-prob. The challenger called the final bet. Rounds that ended on
        a penalty have no outcome; their bets are skipped.
        """
        outcomes = ctx.outcomes
        bets = ctx.bet_history
        while self._seen_outcomes < len(outcomes):
            o = outcomes[self._seen_outcomes]
            key = (o["game"], o["round"])
            round_bets = []
            while self._seen_bets < len(bets):
                e = bets[self._seen_bets]
                if (e["game"], e["round"]) > key:
                    break
                if (e["game"], e["round"]) == key:
                    round_bets.append(e)
                self._seen_bets += 1
            self._consume_round(o, round_bets)
            self._seen_outcomes += 1

    # ── Support belief: their raises, read back at them ───────────────────────

    def _update_held(self, ctx, hand, total) -> None:
        """Track per-opponent per-face support estimates for THIS round.

        Reset when the round turns (a new outcome landed, or the bet key
        moved): hands re-roll, so the prior is uniform — est[f] = d_j*p_hit.
        Then fold in the round's bets:
          raise to (q, f): implied support q - (total-d_j)*p_hit, banked as a
            lower bound (their own certain-dice trick, turned on them) for
            the _held floor, and set/shrunk into the _sup posterior by raise
            class (qty / same-qty low face / same-qty 6) with anti-support
            for the faces they skipped.
        """
        bets = ctx.bet_history
        key = (bets[-1]["game"], bets[-1]["round"]) if len(bets) else None
        if key != self._held_key or len(ctx.outcomes) != self._held_outcomes:
            self._held_key = key
            self._held_outcomes = len(ctx.outcomes)
            self._held = {}
            self._sup = {}
            self._supcache.clear()
            self._held_seen = len(bets)
            while (
                self._held_seen > 0
                and (bets[self._held_seen - 1]["game"], bets[self._held_seen - 1]["round"]) == key
            ):
                self._held_seen -= 1
            self._held_start = self._held_seen  # first bet entry of this round
        stats = ctx.stats
        counts = stats.dice_counts if stats else {}

        def est_for(player):
            est = self._held.get(player)
            if est is None:
                d_j = counts.get(player, 0)
                est = [0.0] + [d_j / 6.0] * 6
                self._held[player] = est
            return est

        def sup_for(player):
            sup = self._sup.get(player)
            if sup is None:
                d_j = counts.get(player, 0)
                sup = [0.0] + [d_j * (2 / 6 if (wild and f != 1) else 1 / 6) for f in range(1, 7)]
                self._sup[player] = sup
            return sup

        # Wild state as of the last folded entry (1-face bids close it). On
        # resume mid-round, rebuild it from the round's processed entries.
        wild = not any(bets[j]["bet"].face == 1 for j in range(self._held_start, self._held_seen))
        # Previous bet this round, for the raise-class read — when resuming
        # mid-round it is the last entry we already folded in.
        prev = None
        if self._held_seen > 0:
            e0 = bets[self._held_seen - 1]
            if (e0["game"], e0["round"]) == key:
                prev = e0
        for i in range(self._held_seen, len(bets)):
            e = bets[i]
            if (e["game"], e["round"]) != key:
                continue
            player, bet = e["player"], e["bet"]
            d_j = counts.get(player, 0)
            if player != self.name and d_j:
                est = est_for(player)
                p_hit = 2 / 6 if (wild and bet.face != 1) else 1 / 6
                implied = bet.quantity - (total - d_j) * p_hit
                est[bet.face] = min(float(d_j), max(est[bet.face], implied))
                if prev is not None:
                    q0, f0 = prev["bet"].quantity, prev["bet"].face
                    if bet.quantity > q0:
                        cls = "qty"
                    elif bet.quantity == q0 and bet.face > f0:
                        cls = "f6" if bet.face == 6 else "f_lo"
                    else:
                        cls = None
                    if cls:
                        sup = sup_for(player)
                        w = (
                            self.SUP_W_QTY
                            if cls == "qty"
                            else (self.SUP_W_F6 if cls == "f6" else self.SUP_W_FLO)
                        )
                        if implied > 0.5:
                            # An informative raise SETS the estimate (a f6
                            # squeeze revises support DOWN from uniform);
                            # a cheap one (implied ~ 0) says nothing.
                            sup[bet.face] = min(float(d_j), w * implied)
                        if cls == "f6":
                            skip = self.SUP_SKIP_F6
                        elif cls == "f_lo":
                            skip = self.SUP_SKIP_FLO
                        else:
                            skip = 0.0
                        for g in range(f0 + 1, bet.face):
                            sup[g] = max(0.0, sup[g] - skip)
                        if cls == "f6" and f0 >= 2:
                            sup[f0] = min(float(d_j), sup[f0] + self.SUP_UNDER_F6)
            prev = e
            if bet.face == 1:
                wild = False  # a 1-face bid closes wilds for the rest of the round
        self._held_seen = len(bets)

    def _held_floor(self, player, face) -> int:
        est = self._held.get(player)
        return int(est[face]) if est is not None else 0

    def _consume_round(self, outcome, round_bets) -> None:
        if not round_bets:
            return
        total = sum(len(h) for h in outcome["hands"].values())

        def wild_at(upto):
            return not any(e["bet"].face == 1 for e in round_bets[:upto])

        # Passes: each bettor after the opener declined to call the prior bet.
        hands = outcome["hands"]
        for i in range(1, len(round_bets)):
            player = round_bets[i]["player"]
            if player == self.name or player not in hands:
                continue
            faced = round_bets[i - 1]["bet"]
            self._record_priv(
                player,
                self._p_priv(hands[player], faced.quantity, faced.face, total, wild_at(i)),
                called=False,
                d=len(hands[player]),
            )
        # The call: the challenger called the final bet.
        challenger = outcome["challenger"]
        if challenger != self.name and challenger in hands:
            final = outcome["final_bet"]
            self._record_priv(
                challenger,
                self._p_priv(
                    hands[challenger],
                    final.quantity,
                    final.face,
                    total,
                    wild_at(len(round_bets)),
                ),
                called=True,
                d=len(hands[challenger]),
            )
        if self.CALL_FIT:
            self._label_honesty(outcome, round_bets, hands, total, wild_at)
        if self.HON_TEMP:
            self._resolve_self(round_bets)

    def _label_honesty(self, outcome, round_bets, hands, total, wild_at) -> None:
        """Per-bidder honesty labels: every opponent bid, scored by the
        judge-seat hold-prob at bid time vs whether the dice backed it.

        The judge is the next bettor (they raised = let it pass) or, for the
        final bid, the challenger. Hold status is deterministic once hands are
        revealed, so raised-over bids are labels too. The curve measures the
        bidder's SELECTION: honest bidders bid into their support (realized
        hold rate above the uniform price), bluffers below it.
        """
        last = len(round_bets) - 1
        for i, e in enumerate(round_bets):
            bidder = e["player"]
            if bidder == self.name or bidder not in hands:
                continue
            judge = round_bets[i + 1]["player"] if i < last else outcome["challenger"]
            if judge not in hands:
                continue
            b = e["bet"]
            w = wild_at(i)
            p = self._p_priv(hands[judge], b.quantity, b.face, total, w)
            match = sum(self._count(list(h), b.face, w) for h in hands.values())
            self._record_hon(bidder, p, failed=match < b.quantity)

    def _record_hon(self, bidder, p, failed) -> None:
        labels = self._hon_labels.setdefault(bidder, [])
        labels.append((p, failed))
        self._hon_total[bidder] = self._hon_total.get(bidder, 0) + 1
        if len(labels) > self.TAU_FIT_CAP:
            del labels[: len(labels) - self.TAU_FIT_CAP]

    def _resolve_self(self, round_bets) -> None:
        """Thermostat observations: our bids this round, called or raised over.

        Every consumed round ended in a call, so our last bid was called iff
        it is the round's final bet; all our earlier ones passed. The FIFO is
        aligned on (qty, face); heads that don't match belong to skipped
        (penalty) rounds and are dropped.
        """
        for i, e in enumerate(round_bets):
            if e["player"] != self.name:
                continue
            b = e["bet"]
            while self._self_bids and self._self_bids[0][:2] != (b.quantity, b.face):
                self._self_bids.pop(0)
            if not self._self_bids:
                return
            p, judge = self._self_bids.pop(0)[2:4]
            if self.TEMP_P_LO <= p <= self.TEMP_P_HI:
                called = i == len(round_bets) - 1
                if called:
                    self._temp_a += 1.0
                else:
                    self._temp_b += 1.0
                if judge is not None:
                    store = self._opp_a if called else self._opp_b
                    store[judge] = store.get(judge, 0.0) + 1.0
                self._temp_obs += 1

    def _p_priv(self, their_hand, qty, face, total, wilds) -> float:
        """P(bid holds) from THEIR seat — exact, since outcomes reveal hands."""
        own = self._count(list(their_hand), face, wilds)
        need = qty - own
        if need <= 0:
            return 1.0
        unseen = total - len(their_hand)
        p_hit = 2 / 6 if (wilds and face != 1) else 1 / 6
        return self._binom_sf(unseen, p_hit, need)

    def _record_priv(self, player, p, called, d) -> None:
        store = self._priv_call if called else self._priv_pass
        s = store.setdefault(player, [0.0, 0])
        s[0] += p
        s[1] += 1
        labels = self._labels.setdefault(player, [])
        labels.append((p, called, d))
        self._labels_total[player] = self._labels_total.get(player, 0) + 1
        if len(labels) > self.TAU_FIT_CAP:
            del labels[: len(labels) - self.TAU_FIT_CAP]

    @staticmethod
    def _sig(z) -> float:
        return 1.0 / (1.0 + pow(2.718281828459045, -max(-60.0, min(60.0, z))))

    @staticmethod
    def _mle(labels) -> tuple[float, float]:
        """Joint (tau, slope) maximum-likelihood fit over (p, called) labels."""
        from math import log

        best, best_ll = None, float("-inf")
        taus = [0.10 + 0.025 * i for i in range(19)]  # 0.10 .. 0.55
        for tau in taus:
            for s in (0.02, 0.05, 0.10):
                ll = 0.0
                for p, called in labels:
                    pc = Littlefinger._sig((tau - p) / s)
                    pc = min(1.0 - 1e-9, max(1e-9, pc))
                    ll += log(pc) if called else log(1.0 - pc)
                if ll > best_ll:
                    best, best_ll = (tau, s), ll
        return best

    @staticmethod
    def _mle_tau(labels, slope) -> float:
        """Tau-only MLE at a fixed slope (the bucketed fit)."""
        from math import log

        best_tau, best_ll = None, float("-inf")
        for tau in [0.10 + 0.025 * i for i in range(19)]:
            ll = 0.0
            for p, called in labels:
                pc = Littlefinger._sig((tau - p) / slope)
                pc = min(1.0 - 1e-9, max(1e-9, pc))
                ll += log(pc) if called else log(1.0 - pc)
            if ll > best_ll:
                best_tau, best_ll = tau, ll
        return best_tau

    def _fit_tau(self, player) -> None:
        """Joint (tau, slope) MLE over the player's recent call/pass labels."""
        labels = self._labels.get(player)
        if not labels or len(labels) < self.TAU_FIT_MIN:
            return
        last = self._fit_n.get(player, 0)
        if len(labels) - last < self.TAU_FIT_EVERY:
            return
        self._fit[player] = self._mle([(p, c) for p, c, _d in labels])
        self._fit_n[player] = len(labels)

    def _fit_dice(self, player) -> None:
        """Per-stack-size bucket fits: five pools (d1..d4, d5+), tau-only at
        the pooled slope. Their threshold drifts with stack size; the bucket
        split halves the label count, so each pool gets fewer parameters —
        the anti-overfit bet."""
        labels = self._labels.get(player)
        if not labels:
            return
        # No new labels since the last scan -> every bucket gate below would
        # fail identically; skip the rebuild. (_fit[player] changes only after
        # new labels too, and _fit_tau runs before us, so s_pool stays fresh.)
        n = self._labels_total.get(player, 0)
        if self._fit_d_scan.get(player) == n:
            return
        self._fit_d_scan[player] = n
        buckets = (
            ("d1", lambda d: d == 1),
            ("d2", lambda d: d == 2),
            ("d3", lambda d: d == 3),
            ("d4", lambda d: d == 4),
            ("d5", lambda d: d >= 5),
        )
        for bucket, pred in buckets:
            sub = [(p, c) for p, c, d in labels if pred(d)]
            key = (player, bucket)
            if len(sub) < self.TAU_FIT_MIN:
                continue
            if len(sub) - self._fit_d_n.get(key, 0) < self.TAU_FIT_EVERY:
                continue
            s_pool = self._fit[player][1] if player in self._fit else self.TAU_SLOPE
            self._fit_d[key] = (self._mle_tau(sub, s_pool), s_pool)
            self._fit_d_n[key] = len(sub)

    @staticmethod
    def _bucket_key(d) -> str:
        return f"d{min(5, max(1, d))}"

    def _tau(self, player, d=None) -> float:
        """Their call threshold on private hold-prob: bucket fit, MLE, closed form."""
        self._fit_tau(player)
        if d is not None:
            self._fit_dice(player)
            fit = self._fit_d.get((player, self._bucket_key(d)))
            if fit is not None:
                return fit[0]
        if player in self._fit:
            return self._fit[player][0]
        c = self._priv_call.get(player)
        p = self._priv_pass.get(player)
        if c and p and c[1] >= self.TAU_MIN_OBS_CALLS and p[1] >= self.TAU_MIN_OBS_PASSES:
            tau = p[0] / p[1] + c[0] / c[1] - 0.5
            return min(0.6, max(0.05, tau))
        return self.TAU_PRIOR

    def _slope(self, player, d=None) -> float:
        self._fit_tau(player)
        if d is not None:
            self._fit_dice(player)
            fit = self._fit_d.get((player, self._bucket_key(d)))
            if fit is not None:
                return fit[1]
        if player in self._fit:
            return self._fit[player][1]
        return self.TAU_SLOPE

    def _p_call_struct(self, stats, player, qty, face, total, wilds) -> float:
        """P(player calls) by replicating their EV calc.

        They call when the bid's hold-prob from THEIR seat drops below their
        personal threshold tau. Their hand is unknown to us, so sum over the
        k matching dice they could hold: for each k, their private p is an
        exact binomial tail over the dice they can't see. When their raises
        have floored them at k_min of this face, the binomial truncates
        there and renormalizes.
        """
        d_j = stats.dice_counts.get(player) if stats else None
        if not d_j:
            q = self._p_holds_public(qty, face, total, wilds)
            return min(1.0, self.POP_BASE_RATE * 2.0 * (1.0 - q))
        p_hit = 2 / 6 if (wilds and face != 1) else 1 / 6
        tau = self._tau(player, d_j)
        slope = self._slope(player, d_j)
        k_min = self._held_floor(player, face)
        if k_min:
            den = self._binom_sf(d_j, p_hit, k_min)
            p_call = 0.0
            for k in range(k_min, d_j + 1):
                pmf = comb(d_j, k) * (p_hit**k) * ((1 - p_hit) ** (d_j - k))
                their_p = self._binom_sf(total - d_j, p_hit, qty - k)
                p_call += pmf * self._sig((tau - their_p) / slope)
            return min(1.0, p_call / den)
        p_call = 0.0
        for k in range(d_j + 1):
            pmf = comb(d_j, k) * (p_hit**k) * ((1 - p_hit) ** (d_j - k))
            their_p = self._binom_sf(total - d_j, p_hit, qty - k)
            p_call += pmf * self._sig((tau - their_p) / slope)
        return min(1.0, p_call)

    def _p_any_call(self, ctx, qty, face, total, wilds) -> float:
        """P(at least one player left to act calls this bid)."""
        players = ctx.round_players
        stats = ctx.stats
        if players and self.name in players:
            idx = players.index(self.name)
            remaining = [players[(idx + 1 + i) % len(players)] for i in range(len(players) - 1)]
            p_none = 1.0
            for p in remaining:
                p_none *= 1.0 - self._p_call_struct(stats, p, qty, face, total, wilds)
            return min(1.0, max(0.0, 1.0 - p_none))
        q = self._p_holds_public(qty, face, total, wilds)
        return min(1.0, self.POP_BASE_RATE * 2.0 * (1.0 - q))

    # ── Probability helpers ───────────────────────────────────────────────────

    @staticmethod
    def _count(hand, face, wilds) -> int:
        return hand.count(face) + (hand.count(1) if (wilds and face != 1) else 0)

    def _p_holds(self, qty, face, hand, total, wilds) -> float:
        """P(bid holds) from our seat: our dice known, the rest uniform."""
        own = self._count(hand, face, wilds)
        need = qty - own
        if need <= 0:
            return 1.0
        unseen = total - len(hand)
        if unseen <= 0:
            return 0.0
        p_hit = 2 / 6 if (wilds and face != 1) else 1 / 6
        return self._binom_sf(unseen, p_hit, need)

    def _sup_suffix(self, ctx, face, total, wilds, hand_len) -> list[float]:
        """Suffix sums of the table's support distribution for one face.

        Each opponent contributes Binomial(d_j, p_adj) with p_adj from their
        support posterior (uniform p_hit when we know nothing); dice not in
        stats lump into one uniform binomial. Convolved exactly (d_j <= 5,
        so the DP is ~1k ops), memoized per (face, wilds, round state) —
        every candidate bid on this face is a different tail cut of the
        same array.
        """
        key = (face, wilds, total, hand_len, self._held_seen, self._held_outcomes)
        cached = self._supcache.get(key)
        if cached is not None:
            return cached
        p_hit = 2 / 6 if (wilds and face != 1) else 1 / 6
        counts = ctx.stats.dice_counts if ctx.stats else {}
        dist = [1.0]
        known = 0

        def convolve(dist, pmf):
            nd = [0.0] * (len(dist) + len(pmf) - 1)
            for s, ps in enumerate(dist):
                if ps == 0.0:
                    continue
                for k, pk in enumerate(pmf):
                    nd[s + k] += ps * pk
            return nd

        for player, d_j in counts.items():
            if player == self.name or d_j <= 0:
                continue
            est = self._sup.get(player)
            mu = est[face] if est is not None else d_j * p_hit
            mu = d_j * p_hit + self.SUP_SHRINK * (mu - d_j * p_hit)
            p_adj = min(0.99, max(0.01, mu / d_j))
            pmf = [comb(d_j, k) * (p_adj**k) * ((1 - p_adj) ** (d_j - k)) for k in range(d_j + 1)]
            dist = convolve(dist, pmf)
            known += d_j
        lump = total - hand_len - known
        if lump > 0:
            pmf = [
                comb(lump, k) * (p_hit**k) * ((1 - p_hit) ** (lump - k)) for k in range(lump + 1)
            ]
            dist = convolve(dist, pmf)
        suffix = [0.0] * (len(dist) + 1)
        acc = 0.0
        for s in range(len(dist) - 1, -1, -1):
            acc += dist[s]
            suffix[s] = acc
        self._supcache[key] = suffix
        return suffix

    def _p_bid_hold(self, ctx, qty, face, hand, total, wilds) -> float:
        """P(our candidate bid holds) against support posteriors, not uniforms."""
        own = self._count(hand, face, wilds)
        need = qty - own
        if need <= 0:
            return 1.0
        suffix = self._sup_suffix(ctx, face, total, wilds, len(hand))
        if need >= len(suffix):
            return 0.0
        return min(1.0, suffix[need])

    def _p_holds_public(self, qty, face, total, wilds) -> float:
        """P(bid holds) with every die unknown — the outside view a caller has."""
        if qty > total:
            return 0.0
        p_hit = 2 / 6 if (wilds and face != 1) else 1 / 6
        return self._binom_sf(total, p_hit, qty)

    def _binom_sf(self, n, p, k) -> float:
        """P(X >= k) for X ~ Binomial(n, p). Memoized: pure in (n, p, k)."""
        key = (n, p, k)
        v = self._bcache.get(key)
        if v is not None:
            return v
        if k <= 0:
            v = 1.0
        elif k > n:
            v = 0.0
        else:
            v = sum(comb(n, i) * (p**i) * ((1 - p) ** (n - i)) for i in range(k, n + 1))
        self._bcache[key] = v
        return v
