from __future__ import annotations

from math import comb

from game.components.bets import Bet
from game.components.context import GameContext


class Varys:
    """
    The spider outlives every sword in the room.

    Everyone else at the table is playing the same game: estimate the dice,
    price the bid, call when the math says the bidder is lying. Their
    information is the bet stream. Varys's information is THEM.

    Phase one — survival. Every completed round is a labelled dataset: each
    bet a player raised over is a bid they declined to call, each challenge
    a bid they called. Because outcomes reveal every hand, each label is
    re-scored with the decider's EXACT private hold-prob, and a per-player
    (tau, slope) call curve is fit by maximum likelihood — how suspicious a
    bid must look from THEIR seat before they reach for liar. Varys then
    bids underneath the table's collective curve: of all legal bids, the one
    least likely to be called, crediting bids that would secretly hold if
    called (the caller bleeds) and bids that leave the next player no cheap
    safe raise. Liar only when calling prices cheaper than the safest raise.

    Phase two — the backstab. Heads-up, every unseen die is theirs, and the
    raise ladder is a finite DAG: Varys solves the whole round by retrograde
    expectimax from the forced call at (total, 6). Their call nodes use
    their fitted curve; their raises are priced as the punishing reply with
    probability HU_RAISE_RHO, the minimal bump otherwise; our nodes take the
    max of calling and raising. Terminals run hot on a called-and-held bid —
    the knife they walk onto.

    He never needed to lie about the dice. He lied about who was playing
    the quiet game.
    """

    name = "Varys"

    # --- Opponent call model: replicate their EV calc ---
    POP_BASE_RATE = 0.3  # challenge-rate prior for unseen players
    # Outcomes reveal every hand at round end, so every past call/pass can be
    # re-scored with the decider's EXACT private hold-prob. For a threshold
    # caller (they call iff their-seat p < tau) samples give
    # mean_pass = (tau+1)/2 and mean_call = tau/2, hence the closed form
    # tau = mean_pass + mean_call - 0.5. The field clusters at tau ~ 0.22
    # (threshold bots) and ~ 0.41 (EV-argmax bots) — this recovers both.
    TAU_PRIOR = 0.3  # threshold assumed before evidence
    TAU_SLOPE = 0.05  # softness of the call step
    TAU_MIN_OBS_CALLS = 3
    TAU_MIN_OBS_PASSES = 10
    # Joint (tau, slope) maximum-likelihood fit per player. The closed form
    # assumes a clean threshold caller; the EV-argmax bots' effective call
    # curve is a blurred step whose width a fixed slope misses.
    TAU_FIT_MIN = 40  # labels before the first fit
    TAU_FIT_EVERY = 25  # new labels between refits
    TAU_FIT_CAP = 400  # labels kept per player

    # --- Survival policy (phase one) ---
    CALL_MARGIN = 0.15  # call liar only when strictly cheaper than the safest raise
    OPEN_CAP_DIV = 2  # opening search: quantities up to total//DIV + 1
    BAIT_WEIGHT = 0.5  # credit for a called-and-held bid (the caller bleeds toward elimination)
    SQUEEZE_WEIGHT = 0.3  # prefer bids that corner the next player (0 = off)

    # --- Heads-up endgame (phase two: the backstab) ---
    EV_WIN_CALL = 1.3  # a challenge resolves in our favor — baited, they bleed
    EV_LOSE_CALL = -1.0  # a challenge resolves against us
    HU_RAISE_RHO = 0.25  # P(they find the punishing raise); else they bump minimally

    def __init__(self) -> None:
        # Per-opponent call/pass labels, re-scored with the decider's exact
        # private hold-prob (their hand is revealed in the outcome) — feeds
        # the closed-form tau estimator and the MLE (tau, slope) fit.
        self._priv_call: dict[str, list[float]] = {}  # [sum, n]
        self._priv_pass: dict[str, list[float]] = {}
        self._labels: dict[str, list[tuple[float, bool]]] = {}
        self._fit: dict[str, tuple[float, float]] = {}  # player -> (tau, slope)
        self._fit_n: dict[str, int] = {}
        self._seen_outcomes = 0
        self._seen_bets = 0
        # Binomial survival memo: (n, p, k) -> exact P(X >= k). The tails are
        # the hot path (every call/hold price), and n <= 45 with p in
        # {1/6, 1/3} means a few thousand distinct values per series.
        self._bcache: dict[tuple[int, float, int], float] = {}

    def algo(self, ctx: GameContext) -> Bet | None:
        hand = ctx.hand
        prior = ctx.prior_bet
        total = ctx.total_dice
        wilds = ctx.stats.ones_are_wild if ctx.stats else True
        self._learn(ctx)

        if len(ctx.round_players) == 2:
            return self._endgame(ctx, hand, prior, total, wilds)
        return self._survive(ctx, hand, prior, total, wilds)

    # ── Phase one: survival ───────────────────────────────────────────────────

    def _survive(self, ctx, hand, prior, total, wilds) -> Bet | None:
        """Minimize P(we lose a die this turn).

        Raising costs us a die exactly when someone calls and the bid fails,
        but a called-and-held bid costs the CALLER a die — every opponent die
        loss brings the heads-up closer:
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

        l_call = self._p_holds(prior.quantity, prior.face, hand, total, wilds)
        min_face = 1 if prior.face == 1 else 2  # survival never re-opens 1s
        best_bid, best_loss = self._safest_bid(
            ctx, hand, prior.quantity, prior.quantity + 1, total, wilds, (prior, min_face)
        )
        if best_bid is None:
            return None  # bid is already (total, 6): calling is the only move
        if l_call < best_loss - self.CALL_MARGIN:
            return None
        return best_bid

    def _safest_bid(self, ctx, hand, q_lo, q_hi, total, wilds, prior_info):
        """Argmin-loss legal bid over quantities [q_lo, q_hi].

        Among faces 2-6 the public hold-prob is identical (same wild math), so
        per quantity only our-seat hold-prob picks the face — except face 1,
        whose public math differs and which survival never volunteers.
        """
        prior, min_face = prior_info if prior_info else (None, 1)
        best_bet, best_loss = None, float("inf")
        pcall_cache = {}  # (qty, p_hit) -> P(any call): faces 2-6 share call math
        for qty in range(q_lo, q_hi + 1):
            faces = range(min_face, 7) if qty == (prior.quantity if prior else qty) else range(2, 7)
            for face in faces:
                if prior is not None and not (
                    qty > prior.quantity or (qty == prior.quantity and face > prior.face)
                ):
                    continue
                p_hold = self._p_holds(qty, face, hand, total, wilds)
                ck = (qty, 2 / 6 if (wilds and face != 1) else 1 / 6)
                p_call = pcall_cache.get(ck)
                if p_call is None:
                    p_call = self._p_any_call(ctx, qty, face, total, wilds)
                    pcall_cache[ck] = p_call
                loss = p_call * (1.0 - p_hold) - self.BAIT_WEIGHT * p_call * p_hold
                if self.SQUEEZE_WEIGHT:
                    # A bid that passes but leaves the next player no cheap
                    # safe raise corners THEM into the bag-holding seat.
                    squeeze = 1.0 - self._best_reraise_pub(qty, face, total, wilds)
                    loss -= self.SQUEEZE_WEIGHT * squeeze * (1.0 - p_call)
                if loss < best_loss - 1e-12:
                    best_bet, best_loss = Bet(qty, face, self.name), loss
        return best_bet, best_loss

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
        to raise rather than call — a pass at the prior bet's public
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
            )

    def _p_priv(self, their_hand, qty, face, total, wilds) -> float:
        """P(bid holds) from THEIR seat — exact, since outcomes reveal hands."""
        own = self._count(list(their_hand), face, wilds)
        need = qty - own
        if need <= 0:
            return 1.0
        unseen = total - len(their_hand)
        p_hit = 2 / 6 if (wilds and face != 1) else 1 / 6
        return self._binom_sf(unseen, p_hit, need)

    def _record_priv(self, player, p, called) -> None:
        store = self._priv_call if called else self._priv_pass
        s = store.setdefault(player, [0.0, 0])
        s[0] += p
        s[1] += 1
        labels = self._labels.setdefault(player, [])
        labels.append((p, called))
        if len(labels) > self.TAU_FIT_CAP:
            del labels[: len(labels) - self.TAU_FIT_CAP]

    @staticmethod
    def _sig(z) -> float:
        return 1.0 / (1.0 + pow(2.718281828459045, -max(-60.0, min(60.0, z))))

    def _fit_tau(self, player) -> None:
        """Joint (tau, slope) MLE over the player's recent call/pass labels."""
        labels = self._labels.get(player)
        if not labels or len(labels) < self.TAU_FIT_MIN:
            return
        last = self._fit_n.get(player, 0)
        if len(labels) - last < self.TAU_FIT_EVERY:
            return
        from math import log

        best, best_ll = None, float("-inf")
        taus = [0.10 + 0.025 * i for i in range(19)]  # 0.10 .. 0.55
        for tau in taus:
            for s in (0.02, 0.05, 0.10):
                ll = 0.0
                for p, called in labels:
                    pc = self._sig((tau - p) / s)
                    pc = min(1.0 - 1e-9, max(1e-9, pc))
                    ll += log(pc) if called else log(1.0 - pc)
                if ll > best_ll:
                    best, best_ll = (tau, s), ll
        self._fit[player] = best
        self._fit_n[player] = len(labels)

    def _tau(self, player) -> float:
        """Their call threshold on private hold-prob: MLE fit, closed form, prior."""
        self._fit_tau(player)
        if player in self._fit:
            return self._fit[player][0]
        c = self._priv_call.get(player)
        p = self._priv_pass.get(player)
        if c and p and c[1] >= self.TAU_MIN_OBS_CALLS and p[1] >= self.TAU_MIN_OBS_PASSES:
            tau = p[0] / p[1] + c[0] / c[1] - 0.5
            return min(0.6, max(0.05, tau))
        return self.TAU_PRIOR

    def _slope(self, player) -> float:
        self._fit_tau(player)
        if player in self._fit:
            return self._fit[player][1]
        return self.TAU_SLOPE

    def _p_call_struct(self, stats, player, qty, face, total, wilds) -> float:
        """P(player calls) by replicating their EV calc.

        They call when the bid's hold-prob from THEIR seat drops below their
        personal threshold tau. Their hand is unknown to us, so sum over the
        k matching dice they could hold: for each k, their private p is an
        exact binomial tail over the dice they can't see.
        """
        d_j = stats.dice_counts.get(player) if stats else None
        if not d_j:
            q = self._p_holds_public(qty, face, total, wilds)
            return min(1.0, self.POP_BASE_RATE * 2.0 * (1.0 - q))
        p_hit = 2 / 6 if (wilds and face != 1) else 1 / 6
        tau = self._tau(player)
        slope = self._slope(player)
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

    # ── Phase two: heads-up backstab ─────────────────────────────────────────

    def _endgame(self, ctx, hand, prior, total, wilds) -> Bet | None:
        """Aggressive exact play with one opponent left.

        Every unseen die is theirs, so hold-probs are exact and their call
        decision is modeled over their possible hands. EV_WIN_CALL runs hot:
        a bid they cannot resist calling, from a hand that secretly carries
        it, is worth more than a quiet pass. That is the whole con — they
        spent the game learning a spider who never raised, and now the raise
        is the trap.
        """
        d_opp = total - len(hand)

        ev_liar = float("-inf")
        if prior is not None:
            p_prior = self._p_holds(prior.quantity, prior.face, hand, total, wilds)
            p_prior = self._p_holds_open(ctx, prior, hand, d_opp, total, wilds, p_prior)
            ev_liar = p_prior * self.EV_LOSE_CALL + (1.0 - p_prior) * self.EV_WIN_CALL

        return self._endgame_deep(ctx, hand, prior, total, wilds, d_opp, ev_liar)

    def _deep_ladder(self, ctx, hand, d_opp, total, wilds):
        """Retrograde expectimax over the whole raise ladder (heads-up).

        Rungs are totally ordered and 1s close permanently once a non-1 face
        is bid, so the round is a finite DAG solved backwards from (total, 6).
        Their nodes: fitted call curve plus, per possible hand-count k, the
        raise that leaves us the worst continuation (zero-sum approximation),
        aggregated over the binomial. Our nodes: max of call / best raise."""
        opp = next((p for p in ctx.round_players if p != self.name), None)
        tau = self._tau(opp) if opp else self.TAU_PRIOR
        slope = self._slope(opp) if opp else self.TAU_SLOPE
        d_us = len(hand)
        rungs = [(q, f) for q in range(1, total + 1) for f in range(1, 7)]
        counts = {
            f: hand.count(f) + (hand.count(1) if (wilds and f != 1) else 0) for f in range(1, 7)
        }

        def p_hit(f):
            return 2 / 6 if (wilds and f != 1) else 1 / 6

        children = {}
        for i, (q, f) in enumerate(rungs):
            for c in (True, False):
                if f == 1 and c:
                    continue  # 1s rungs only exist before closure
                ch = []
                for j in range(i + 1, len(rungs)):
                    f2 = rungs[j][1]
                    c2 = c or f2 != 1
                    if not (c2 and f2 == 1):
                        ch.append((j, c2))
                children[(i, c)] = ch
        v_us, v_them = {}, {}
        for i in range(len(rungs) - 1, -1, -1):
            q, f = rungs[i]
            for c in (True, False):
                if f == 1 and c:
                    continue
                ph = p_hit(f)
                c_us = counts[f]
                pmf = [
                    comb(d_opp, k) * (ph**k) * ((1 - ph) ** (d_opp - k)) for k in range(d_opp + 1)
                ]
                ch = children[(i, c)]
                call_us = sum(
                    pmf[k] * (self.EV_WIN_CALL if c_us + k < q else self.EV_LOSE_CALL)
                    for k in range(d_opp + 1)
                )
                best_raise = max((v_them[s] for s in ch), default=None)
                v_us[(i, c)] = max(call_us, best_raise) if best_raise is not None else call_us
                worst = min((v_us[s] for s in ch), default=None)
                lazy = v_us[ch[0]] if ch else None  # ch ascends: ch[0] = minimal raise
                rho = self.HU_RAISE_RHO
                val = 0.0
                for k in range(d_opp + 1):
                    their_p = self._binom_sf(d_us, ph, q - k)
                    pc = self._sig((tau - their_p) / slope)
                    call_val = self.EV_WIN_CALL if c_us + k >= q else self.EV_LOSE_CALL
                    punish = worst if worst is not None else call_val
                    bump = lazy if lazy is not None else call_val
                    raise_val = rho * punish + (1.0 - rho) * bump
                    val += pmf[k] * (pc * call_val + (1.0 - pc) * raise_val)
                v_them[(i, c)] = val
        return v_them, children, rungs

    def _endgame_deep(self, ctx, hand, prior, total, wilds, d_opp, ev_liar):
        v_them, children, rungs = self._deep_ladder(ctx, hand, d_opp, total, wilds)
        idx = {rf: i for i, rf in enumerate(rungs)}
        if prior is None:
            best_bet, best_ev = None, float("-inf")
            for q in range(1, total + 1):
                for f in range(1, 7):
                    val = v_them[(idx[(q, f)], f != 1)]
                    if val > best_ev:
                        best_bet, best_ev = Bet(q, f, self.name), val
            return best_bet
        i0, c0 = idx[(prior.quantity, prior.face)], prior.face != 1
        best_bet, best_ev = None, float("-inf")
        for j, c2 in children[(i0, c0)]:
            val = v_them[(j, c2)]
            if val > best_ev:
                q2, f2 = rungs[j]
                best_bet, best_ev = Bet(q2, f2, self.name), val
        if best_bet is None or ev_liar >= best_ev:
            return None
        return best_bet

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

    def _p_holds_open(self, ctx, prior, hand, d_opp, total, wilds, p_uniform) -> float:
        """P(their bid holds) when prior is their OPENING bid of the round.

        An opener is a function of their hand: q ~= own + d_us*p_hit*mult,
        so the opener itself is evidence about their support. Recover mult
        from their observed opening_aggression, back out the implied own
        count k_hat = q - d_us*p_hit*mult, and re-price the hold over the
        truncated binomial K >= k_hat. Anything but their round opener ->
        the uniform price.
        """
        bets = ctx.bet_history
        if not len(bets):
            return p_uniform
        key = (bets[-1]["game"], bets[-1]["round"])
        first = None
        for e in reversed(bets):
            if (e["game"], e["round"]) != key:
                break
            first = e
        if first is None or first["player"] != prior.player:
            return p_uniform
        fb = first["bet"]
        if fb.quantity != prior.quantity or fb.face != prior.face:
            return p_uniform
        p_hit = 2 / 6 if (wilds and prior.face != 1) else 1 / 6
        d_us = len(hand)
        mult = 0.7
        oa = ctx.stats.opening_aggression.get(prior.player) if ctx.stats else None
        if oa and d_us and p_hit:
            # oa = mean(q_open / total); with q ~= d_opp*p_hit + d_us*p_hit*mult
            # expected, solve for their mult from the observed average.
            est = (oa * total - d_opp * p_hit) / (d_us * p_hit)
            if 0.2 <= est <= 2.0:
                mult = est
        k_hat = max(0, round(prior.quantity - d_us * p_hit * mult))
        our = self._count(hand, prior.face, wilds)
        den = self._binom_sf(d_opp, p_hit, k_hat)
        if den <= 0:
            return p_uniform
        p_open = self._binom_sf(d_opp, p_hit, max(k_hat, prior.quantity - our)) / den
        return min(1.0, p_open)

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
