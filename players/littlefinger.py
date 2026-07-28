from __future__ import annotations

from math import comb

from game.components.bets import Bet
from game.components.context import GameContext


def _solve3(h, g):
    """3x3 Gaussian elimination with partial pivot; None if singular."""
    m = [row[:] + [g[i]] for i, row in enumerate(h)]
    for col in range(3):
        piv = max(range(col, 3), key=lambda r: abs(m[r][col]))
        if abs(m[piv][col]) < 1e-12:
            return None
        m[col], m[piv] = m[piv], m[col]
        for r in range(col + 1, 3):
            f = m[r][col] / m[col][col]
            for c in range(col, 4):
                m[r][c] -= f * m[col][c]
    x = [0.0] * 3
    for r in (2, 1, 0):
        x[r] = (m[r][3] - sum(m[r][c] * x[c] for c in range(r + 1, 3))) / m[r][r]
    return x


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

    # --- Opponent call model: per-opponent fitted call thresholds ---
    POP_BASE_RATE = 0.3  # challenge-rate prior for unseen players
    TAU_PRIOR = 0.3
    TAU_SLOPE = 0.05
    TAU_MIN_OBS_CALLS = 3
    TAU_MIN_OBS_PASSES = 10
    TAU_FIT_MIN = 40  # labels before the first MLE fit
    TAU_FIT_EVERY = 25  # new labels between refits
    TAU_FIT_CAP = 400  # labels kept per player

    # --- Survival policy ---
    CALL_MARGIN = 0.15  # call liar only when strictly cheaper than the safest raise
    OPEN_CAP_DIV = 2  # opening search: quantities up to total//DIV + 1
    BAIT_WEIGHT = 0.2  # credit for a called-and-held bid
    SQUEEZE_WEIGHT = 0.35  # prefer bids that corner the next player

    # --- Poison band: among near-tied bids take the one our hand least supports ---
    POISON_EPS = 0.05
    POISON_MIN_DICE = 3  # below this, play honest (short stacks get believed)

    # --- Poison gate: skip the poison pick vs judges whose claim-pressure
    # coefficient (per-opponent online IRLS) is confidently negative ---
    POGATE_Z = -3.0  # gate fires below this z-score on the claim coef
    POGATE_CAP = 2000  # per-opponent label window (FIFO)
    POGATE_EVERY = 100  # refit cadence (new labels)
    POGATE_MIN = 400  # min labels before the fit is trusted

    # --- Variance posture: behind on dice, the band pick buys a coin flip ---
    VAR_EPS = 0.05

    # --- Call door: per-bidder honesty curves + asymmetric squeeze read ---
    CALL_FIT_SHRINK = 40.0  # uniform pseudo-labels blended into each curve
    CALL_SUP_W = 0.5  # their sup posterior may lower the price, never raise it

    # --- Support posterior: per-opponent per-face estimates, reset per round ---
    SUP_W_QTY = 1.0  # qty raise to f
    SUP_W_FLO = 0.9  # same-qty raise to f<6
    SUP_W_F6 = 0.35  # same-qty raise to 6 (the squeeze class)
    SUP_SKIP_FLO = 0.6  # anti-support per skipped face, same-qty to f<6
    SUP_SKIP_F6 = 0.3  # anti-support per skipped face, same-qty to 6
    SUP_UNDER_F6 = 0.2  # support under the bid (f0) after a same-qty 6-raise
    SUP_REV = 1.2  # revisit bonus: raising back to a face already bid this round
    SUP_SHRINK = 0.5  # winner's-curse shrink toward uniform
    SUP_REL_SHRINK = 5.0  # pseudo-samples pulling tell reliability to 1.0

    # --- Call-door Platt recalibration: p' = sig(A + B*logit(p)) ---
    CAL_A = 0.33
    CAL_B = 1.35

    # --- Dice-diff push: among near-tied candidates take max qty ---
    DPUSH_N = 5  # push gate: live players >= this
    DPUSH_EPS = 0.02  # tie window in expected-loss units
    DPUSH_GAP = 1.5  # max public gap allowed into the push band

    def __init__(self) -> None:
        # Per-opponent call/pass labels, re-scored with the decider's exact
        # private hold-prob (their hand is revealed in the outcome). Each
        # label also carries the decider's dice count for the bucketed fit.
        self._priv_call: dict[str, list[float]] = {}  # [sum, n]
        self._priv_pass: dict[str, list[float]] = {}
        self._labels: dict[str, list[tuple[float, bool, int]]] = {}
        self._pgap: dict[str, list] = {}  # player -> [(p, claim, called)] window
        self._pgfit: dict[str, tuple] = {}  # player -> (claim coef, se, n at fit)
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
        self._sup_sig: dict[str, set[int]] = {}  # faces they bid this round
        self._supcache: dict[tuple, list[float]] = {}
        # Tell reliability: (player, cls) -> [sum of actual/implied, n].
        # _rel_events: informative raises (key, player, cls, implied, face,
        # wild) awaiting their round's reveal for scoring.
        self._rel: dict[tuple[str, str], list[float]] = {}
        self._rel_events: list[tuple] = []
        # Binomial survival memo: (n, p, k) -> exact P(X >= k). The tails are
        # the hot path (every call/hold price), and n <= 45 with p in
        # {1/6, 1/3} means a few thousand distinct values per series.
        self._bcache: dict[tuple[int, float, int], float] = {}
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
        return self._survive(ctx, hand, prior, total, wilds)

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
        honesty curve, then the asymmetric squeeze read: their support
        posterior may lower the price, never raise it.
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
        cand = []  # (loss, bet, p_hold, p_call) for every legal bid
        pcall_cache = {}  # (qty, p_hit) -> P(any call): faces 2-6 share call math
        judge = self._judge(ctx)
        n_live = len(ctx.round_players) if ctx.round_players else 0
        for qty in range(q_lo, q_hi + 1):
            faces = range(min_face, 7) if qty == (prior.quantity if prior else qty) else range(2, 7)
            for face in faces:
                if prior is not None and not (
                    qty > prior.quantity or (qty == prior.quantity and face > prior.face)
                ):
                    continue
                p_hold = self._p_bid_hold(ctx, qty, face, hand, total, wilds)
                bet = Bet(qty, face, self.name)
                ck = (qty, self._p_hit(face, wilds))
                p_call = pcall_cache.get(ck)
                if p_call is None:
                    p_call = self._p_any_call(ctx, qty, face, total, wilds)
                    pcall_cache[ck] = p_call
                loss = p_call * ((1.0 - p_hold) - self.BAIT_WEIGHT * p_hold)
                if self.SQUEEZE_WEIGHT:
                    # A bid that passes but leaves the next player no cheap
                    # safe raise corners THEM into the bag-holding seat.
                    sq = 1.0 - self._best_reraise_pub(qty, face, total, wilds)
                    loss -= self.SQUEEZE_WEIGHT * sq * (1.0 - p_call)
                cand.append((loss, bet, p_hold, p_call))
                if loss < best_loss - 1e-12:
                    best_bet, best_loss = bet, loss
        counts = ctx.stats.dice_counts if ctx.stats else {}
        behind = False
        if counts:
            alive = sum(1 for v in counts.values() if v > 0)
            behind = total > 0 and alive > 0 and len(hand) * alive < total
        if behind:
            # Trailing: take the max-variance bid in the band — the grind has
            # no edge, so buy a coin flip. Replaces the poison pick.
            band = [c for c in cand if c[0] <= best_loss + self.VAR_EPS]
            if len(band) > 1:
                best_bet = max(
                    band,
                    key=lambda c: (
                        c[3] - (c[3] * (2.0 * c[2] - 1.0)) ** 2,
                        -c[0],
                        (-c[1].quantity, -c[1].face),
                    ),
                )[1]
        elif len(hand) >= self.POISON_MIN_DICE and self._poison_pays(judge):
            # Bids within EPS of optimal cost us the same in expectation, but
            # not THEM: the pool inverts our first bid of the round into
            # "certain" dice. Take the one our hand least supports.
            band = [c for c in cand if c[0] <= best_loss + self.POISON_EPS]
            if len(band) > 1:
                best_bet = min(
                    band,
                    key=lambda c: (
                        self._count(hand, c[1].face, wilds),
                        c[0],
                        (c[1].quantity, c[1].face),
                    ),
                )[1]
        else:
            # The push: among near-tied candidates take max qty — a tied
            # higher-qty bid must be better backed, so the tiebreak is a
            # selectivity filter that also buys rung advancement.
            band = [c for c in cand if c[0] <= best_loss + self.DPUSH_EPS]
            if n_live >= self.DPUSH_N:
                pushable = [
                    c
                    for c in band
                    if c[1].quantity - total * self._p_hit(c[1].face, wilds) <= self.DPUSH_GAP
                ]
                if pushable:
                    best_bet = max(
                        pushable,
                        key=lambda c: (c[1].quantity, -c[0], -c[1].face),
                    )[1]
        return best_bet, best_loss

    def _poison_pays(self, judge) -> bool:
        """Skip the min-support pick vs judges whose claim coefficient is
        confidently negative — they go passive under claim pressure, so the
        unsupported-face bid buys no bait into them. ON until the fit has
        POGATE_MIN labels."""
        if judge is None:
            return True
        fit = self._pgfit.get(judge)
        if fit is None or fit[2] < self.POGATE_MIN:
            return True
        coef, se, _n = fit
        return not (coef < 0.0 and se > 0.0 and coef / se < self.POGATE_Z)

    def _judge(self, ctx):
        """The only opponent who can call our next bid: next live player clockwise."""
        players = ctx.round_players
        if players and len(players) > 1 and self.name in players:
            return players[(players.index(self.name) + 1) % len(players)]
        return None

    def _best_reraise(self, qty, face, total, wilds) -> tuple[int, int, float]:
        """The next player's best cheap raise over (qty, face) and its public
        hold-prob: the minimal bump (same qty, next face up) or the lowest
        qty raise, whichever holds better."""
        min_face = 2 if wilds else 1
        options = [(qty + 1, min_face)]
        if face < 6:
            options.append((qty, face + 1))
        q2, f2 = max(options, key=lambda bf: self._p_holds_public(bf[0], bf[1], total, wilds))
        return q2, f2, self._p_holds_public(q2, f2, total, wilds)

    def _best_reraise_pub(self, qty, face, total, wilds) -> float:
        """Public hold-prob of the next player's best cheap raise over (qty, face)."""
        return self._best_reraise(qty, face, total, wilds)[2]

    def _seat_order(self, ctx) -> list:
        """Live seats after us, clockwise — the order callers act in."""
        players = ctx.round_players
        if players and self.name in players and len(players) > 1:
            idx = players.index(self.name)
            return [players[(idx + 1 + i) % len(players)] for i in range(len(players) - 1)]
        return []

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
            self._sup_sig = {}
            self._supcache.clear()
            self._held_seen = len(bets)
            while (
                self._held_seen > 0
                and (bets[self._held_seen - 1]["game"], bets[self._held_seen - 1]["round"]) == key
            ):
                self._held_seen -= 1
            self._held_start = self._held_seen  # first bet_history index of the current round
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
                sup = [0.0] + [d_j * self._p_hit(f, wild) for f in range(1, 7)]
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
                implied = bet.quantity - (total - d_j) * self._p_hit(bet.face, wild)
                est[bet.face] = min(float(d_j), max(est[bet.face], implied))
                faces = self._sup_sig.setdefault(player, set())
                revisit = bet.face in faces
                faces.add(bet.face)
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
                            rel = self._rel_for(player, cls)
                            sup[bet.face] = min(float(d_j), w * implied * rel)
                            self._rel_events.append((key, player, cls, implied, bet.face, wild))
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
                        if revisit and self.SUP_REV:
                            # Back to a face they already bid — the pattern is
                            # the evidence, even when implied says nothing.
                            sup[bet.face] = min(float(d_j), sup[bet.face] + self.SUP_REV)
            prev = e
            if bet.face == 1:
                wild = False  # a 1-face bid closes wilds for the rest of the round
        self._held_seen = len(bets)

    def _held_floor(self, player, face) -> int:
        est = self._held.get(player)
        return int(est[face]) if est is not None else 0

    def _rel_score(self, player, cls, implied, actual) -> None:
        """Fold one revealed informative raise into the reliability stats."""
        s = self._rel.setdefault((player, cls), [0.0, 0.0])
        s[0] += min(3.0, actual / implied)
        s[1] += 1.0
        if s[1] > 240.0:  # cap: halve both so the mean can drift
            s[0] *= 0.5
            s[1] *= 0.5

    def _rel_for(self, player, cls) -> float:
        """Reliability multiplier for this raiser's class, shrunk to 1.0."""
        s = self._rel.get((player, cls))
        if s is None:
            return 1.0
        r = (s[0] + self.SUP_REL_SHRINK) / (s[1] + self.SUP_REL_SHRINK)
        return min(1.6, max(0.3, r))

    def _consume_round(self, outcome, round_bets) -> None:
        if not round_bets:
            return
        total = sum(len(h) for h in outcome["hands"].values())

        def wild_at(upto):
            return not any(e["bet"].face == 1 for e in round_bets[:upto])

        def claim_at(upto, face, decider):
            # Same-face claim pressure on the judged bid: summed qty of
            # same-face round bids by others, per unseen die of the decider.
            unseen = max(1, total - len(hands[decider]))
            return (
                sum(
                    e["bet"].quantity
                    for e in round_bets[:upto]
                    if e["bet"].face == face and e["player"] != decider
                )
                / unseen
            )

        # Passes: each bettor after the opener declined to call the prior bet.
        hands = outcome["hands"]
        if self._rel_events:
            # Score this round's informative raises against the reveal. Keep
            # only events from later rounds (folded before the outcome
            # landed); past-round events can never match and are dropped.
            rkey = (outcome["game"], outcome["round"])
            keep = []
            for k, player, cls, implied, face, w in self._rel_events:
                if k != rkey or player not in hands:
                    if k > rkey:
                        keep.append((k, player, cls, implied, face, w))
                    continue
                self._rel_score(player, cls, implied, self._count(list(hands[player]), face, w))
            self._rel_events = keep
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
                claim=claim_at(i, faced.face, player),
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
                claim=claim_at(len(round_bets), final.face, challenger),
            )
        self._label_honesty(outcome, round_bets, hands, total, wild_at)

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

    def _p_priv(self, their_hand, qty, face, total, wilds) -> float:
        """P(bid holds) from THEIR seat — exact, since outcomes reveal hands."""
        own = self._count(list(their_hand), face, wilds)
        need = qty - own
        if need <= 0:
            return 1.0
        unseen = total - len(their_hand)
        return self._binom_sf(unseen, self._p_hit(face, wilds), need)

    def _record_priv(self, player, p, called, d, claim=None) -> None:
        store = self._priv_call if called else self._priv_pass
        s = store.setdefault(player, [0.0, 0])
        s[0] += p
        s[1] += 1
        labels = self._labels.setdefault(player, [])
        labels.append((p, called, d))
        self._labels_total[player] = self._labels_total.get(player, 0) + 1
        if len(labels) > self.TAU_FIT_CAP:
            del labels[: len(labels) - self.TAU_FIT_CAP]
        if claim is not None and 0.076 <= p <= 0.378:
            g = self._pgap.setdefault(player, [])
            g.append((p, claim, called))
            if len(g) > self.POGATE_CAP:
                del g[: len(g) - self.POGATE_CAP]
            fit = self._pgfit.get(player)
            if fit is None or len(g) - fit[2] >= self.POGATE_EVERY:
                self._pgate_fit(player)

    def _pgate_fit(self, player) -> None:
        """IRLS refit of the player's claim coefficient over the window.

        call ~ 1 + logit(p) + claim — the audit estimator, online. Only the
        claim coef and its SE are kept; the gate reads sign + z-score.
        """
        from math import log

        rows = self._pgap.get(player)
        if not rows:
            return
        x = [[0.0] * 3 for _ in range(3)]
        beta = [0.0, 0.0, 0.0]
        for _ in range(15):
            grad = [0.0, 0.0, 0.0]
            for r in range(3):
                x[r] = [0.0, 0.0, 0.0]
            for p, claim, called in rows:
                lp = log(p / (1.0 - p))
                z = max(-30.0, min(30.0, beta[0] + beta[1] * lp + beta[2] * claim))
                pr = self._sig(z)
                w = max(1e-9, pr * (1.0 - pr))
                r_ = (1.0 if called else 0.0) - pr
                grad[0] += r_
                grad[1] += lp * r_
                grad[2] += claim * r_
                x[0][0] += w
                x[0][1] += w * lp
                x[0][2] += w * claim
                x[1][1] += w * lp * lp
                x[1][2] += w * lp * claim
                x[2][2] += w * claim * claim
            x[1][0], x[2][0], x[2][1] = x[0][1], x[0][2], x[1][2]
            step = _solve3(x, grad)
            if step is None:
                return
            for a in range(3):
                beta[a] += step[a]
        det = (
            x[0][0] * (x[1][1] * x[2][2] - x[1][2] * x[1][2])
            - x[0][1] * (x[0][1] * x[2][2] - x[1][2] * x[0][2])
            + x[0][2] * (x[0][1] * x[1][2] - x[1][1] * x[0][2])
        )
        if abs(det) < 1e-18:
            return
        se = (max(0.0, (x[0][0] * x[1][1] - x[0][1] * x[0][1]) / det)) ** 0.5
        self._pgfit[player] = (beta[2], se, len(rows))

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
        p_hit = self._p_hit(face, wilds)
        tau = self._tau(player, d_j)
        slope = self._slope(player, d_j)
        k_min = self._held_floor(player, face)
        den = self._binom_sf(d_j, p_hit, k_min) if k_min else 1.0
        pmfs = self._pmf(d_j, p_hit)
        p_call = 0.0
        for k in range(k_min, d_j + 1):
            their_p = self._binom_sf(total - d_j, p_hit, qty - k)
            p_call += pmfs[k] * self._sig((tau - their_p) / slope)
        p = min(1.0, p_call / den)
        return self._platt(p)

    def _platt(self, p: float) -> float:
        """Audit-fitted recalibration of the call-door mixture."""
        from math import log

        p = min(1.0 - 1e-9, max(1e-9, p))
        return self._sig(self.CAL_A + self.CAL_B * log(p / (1.0 - p)))

    def _p_any_call(self, ctx, qty, face, total, wilds) -> float:
        """P(at least one player left to act calls this bid)."""
        players = ctx.round_players
        if players and self.name in players:
            p_none = 1.0
            for p in self._seat_order(ctx):
                p_none *= 1.0 - self._p_call_struct(ctx.stats, p, qty, face, total, wilds)
            return min(1.0, max(0.0, 1.0 - p_none))
        q = self._p_holds_public(qty, face, total, wilds)
        return min(1.0, self.POP_BASE_RATE * 2.0 * (1.0 - q))

    # ── Probability helpers ───────────────────────────────────────────────────

    @staticmethod
    def _count(hand, face, wilds) -> int:
        return hand.count(face) + (hand.count(1) if (wilds and face != 1) else 0)

    @staticmethod
    def _p_hit(face, wilds) -> float:
        return 2 / 6 if (wilds and face != 1) else 1 / 6

    @staticmethod
    def _pmf(n, p) -> list[float]:
        return [comb(n, k) * (p**k) * ((1 - p) ** (n - k)) for k in range(n + 1)]

    def _p_holds(self, qty, face, hand, total, wilds) -> float:
        """P(bid holds) from our seat: our dice known, the rest uniform."""
        own = self._count(hand, face, wilds)
        need = qty - own
        if need <= 0:
            return 1.0
        unseen = total - len(hand)
        if unseen <= 0:
            return 0.0
        return self._binom_sf(unseen, self._p_hit(face, wilds), need)

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
        p_hit = self._p_hit(face, wilds)
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
            dist = convolve(dist, self._pmf(d_j, p_adj))
            known += d_j
        lump = total - hand_len - known
        if lump > 0:
            dist = convolve(dist, self._pmf(lump, p_hit))
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
