from __future__ import annotations

from math import comb, log

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


class Retep:
    """
    My name is Retep, and I am evil.

    Gen 3 Liar's Dice engine built to counter both Gen 1 (EV-scan + rational
    opener inversion) and Gen 2 (bleed-race + poison-band) strategies purely
    by profiling live opponent tendencies from revealed hands:

    1. Live Tendency Profiling (_tend_score / _tend_shift):
       Scores every opponent's opening and low-pressure bids against revealed
       hands at round end, separating healthy stacks (d >= 3, not trailing)
       from short stacks. Positive shifts identify honest/EV openers (whose
       first bid and early raises carry genuine face support above uniform);
       negative shifts unmask poison-band bots (whose low-risk bids deliberately
       pick their least-supported face).

    2. Conservation of Dice & Continuous Support Posteriors (_update_held):
       Folds opening bids (which Gen 2 ignored) and raises into per-opponent
       support vectors, redistributing probability mass across non-bid faces
       via conservation of dice, and flooring honest raisers above uniform so
       early raises with 0.5 < implied < unif never artificially depress their
       support estimate.

    3. Independent Pre-Prior Call Auditing (PRIOR_SELF_DISCOUNT):
       When pricing a Liar call on `prior`, discounts `prior.player`'s
       uncorroborated self-claim toward their pre-bid support (`_prior_pre_sup`)
       unless they revisited a face they already backed earlier in the round —
       preventing desperate quantity jumps from grading their own homework.

    4. First-Bid-Only Poisoning & Heads-Up Gear Shift:
       Restricts anti-support poisoning to Retep's first bid of the round in
       3+ player tables (the exact window Gen 1's _round_opening_bids records),
       switching to pure hold/push optimization on later orbits and tightening
       call margins and bait weights in 1v1 endgames.
    """

    name = "Retep"
    avatar = "ohkyed3h/retep_avatar.jpg"

    # --- Opponent call model: per-opponent fitted call thresholds ---
    POP_BASE_RATE = 0.3
    TAU_PRIOR = 0.3
    TAU_SLOPE = 0.05
    TAU_MIN_OBS_CALLS = 3
    TAU_MIN_OBS_PASSES = 10
    TAU_FIT_MIN = 40
    TAU_FIT_EVERY = 25
    TAU_FIT_CAP = 400

    # --- Survival & Endgame policy ---
    CALL_MARGIN = 0.15
    HU_CALL_MARGIN = 0.06  # tighter call margin in 1v1 when all unseen dice are theirs
    OPEN_CAP_DIV = 2
    BAIT_WEIGHT = 0.20
    HU_BAIT_WEIGHT = 0.45  # in 1v1, a called-and-held bid directly bleeds our sole rival
    SQUEEZE_WEIGHT = 0.35

    # --- Poison band: only on our first bid of the round (when inverters listen) ---
    POISON_EPS = 0.05
    POISON_MIN_DICE = 3
    FIRST_BID_POISON_ONLY = True

    # --- Poison gate (online IRLS over judge's claim-pressure response) ---
    POGATE_Z = -3.0
    POGATE_CAP = 2000
    POGATE_EVERY = 100
    POGATE_MIN = 400

    # --- Variance posture when trailing on dice ---
    VAR_EPS = 0.05

    # --- Call door: per-bidder honesty curves + asymmetric support read ---
    CALL_FIT_SHRINK = 40.0
    CALL_SUP_W = 0.55
    PRIOR_SELF_DISCOUNT = 0.50  # discount uncorroborated self-claim on the bid being judged

    # --- Support posterior: per-opponent per-face estimates, reset per round ---
    SUP_W_QTY = 1.0
    SUP_W_FLO = 0.9
    SUP_W_F6 = 0.35
    SUP_SKIP_FLO = 0.6
    SUP_SKIP_F6 = 0.3
    SUP_UNDER_F6 = 0.2
    SUP_REV = 1.2
    SUP_SHRINK = 0.55
    SUP_REL_SHRINK = 5.0

    # --- Live tendency tracking for openings & low/mid-pressure raises ---
    TEND_SHRINK = 6.0  # pseudo-samples shrinking signed shift toward 0
    TEND_CONSERVE = 0.20  # fraction of face shift redistributed to non-bid faces

    # --- Call-door Platt recalibration: p' = sig(A + B*logit(p)) ---
    CAL_A = 0.33
    CAL_B = 1.35

    # --- Dice-diff push: among near-tied candidates take max qty ---
    DPUSH_N = 5
    DPUSH_EPS = 0.02
    DPUSH_GAP = 1.5

    def __init__(self) -> None:
        self._priv_call: dict[str, list[float]] = {}
        self._priv_pass: dict[str, list[float]] = {}
        self._labels: dict[str, list[tuple[float, bool, int]]] = {}
        self._pgap: dict[str, list] = {}
        self._pgfit: dict[str, tuple] = {}
        self._fit: dict[str, tuple[float, float]] = {}
        self._fit_n: dict[str, int] = {}
        self._fit_d: dict[tuple[str, str], tuple[float, float]] = {}
        self._fit_d_n: dict[tuple[str, str], int] = {}
        self._labels_total: dict[str, int] = {}
        self._fit_d_scan: dict[str, int] = {}
        self._seen_outcomes = 0
        self._seen_bets = 0

        # Round-level support beliefs
        self._held: dict[str, list[float]] = {}
        self._held_key = None
        self._held_seen = 0
        self._held_start = 0
        self._held_outcomes = 0
        self._sup: dict[str, list[float]] = {}
        self._sup_sig: dict[str, set[int]] = {}
        self._supcache: dict[tuple, list[float]] = {}
        self._our_round_bids: int = 0
        self._prior_pre_sup: float | None = None
        self._prior_revisit: bool = False

        # Tell reliability for informative raises (implied > 0.5)
        self._rel: dict[tuple[str, str], list[float]] = {}
        self._rel_events: list[tuple] = []

        # Signed excess support tendency for openings & raises:
        # key = (player, mode) where mode in ("open_hi", "open_lo", "cheap_hi", "cheap_lo")
        # value = [sum_excess_per_die, count]
        self._tend: dict[tuple[str, str], list[float]] = {}
        self._tend_events: list[tuple] = []

        self._bcache: dict[tuple[int, float, int], float] = {}

        # Per-bidder honesty curve state
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

    # ── Core decision loop ────────────────────────────────────────────────────

    def _survive(self, ctx, hand, prior, total, wilds) -> Bet | None:
        n_live = len(ctx.round_players) if ctx.round_players else 2
        if prior is None:
            best, _ = self._safest_bid(
                ctx, hand, 1, min(total, total // self.OPEN_CAP_DIV + 1), total, wilds, None
            )
            return best

        l_call = self._l_call(ctx, prior, hand, total, wilds)
        min_face = 1 if prior.face == 1 else 2
        q_hi = min(total, prior.quantity + (2 if n_live == 2 else 1))
        best_bid, best_loss = self._safest_bid(
            ctx, hand, prior.quantity, q_hi, total, wilds, (prior, min_face)
        )
        if best_bid is None:
            return None
        margin = self.HU_CALL_MARGIN if n_live == 2 else self.CALL_MARGIN
        if l_call < best_loss - margin:
            return None
        return best_bid

    def _l_call(self, ctx, prior, hand, total, wilds) -> float:
        cost = self._p_hold_faced(
            prior.player, self._p_holds(prior.quantity, prior.face, hand, total, wilds)
        )
        if self.CALL_SUP_W:
            sup_p = self._sup.get(prior.player)
            if (
                self.PRIOR_SELF_DISCOUNT
                and sup_p is not None
                and self._prior_pre_sup is not None
                and not self._prior_revisit
                and sup_p[prior.face] > self._prior_pre_sup
            ):
                saved = sup_p[prior.face]
                sup_p[prior.face] = (
                    self.PRIOR_SELF_DISCOUNT * self._prior_pre_sup
                    + (1.0 - self.PRIOR_SELF_DISCOUNT) * saved
                )
                self._supcache.clear()
                p_sup = self._p_bid_hold(ctx, prior.quantity, prior.face, hand, total, wilds)
                sup_p[prior.face] = saved
                self._supcache.clear()
            else:
                p_sup = self._p_bid_hold(ctx, prior.quantity, prior.face, hand, total, wilds)
            cost = min(cost, (1.0 - self.CALL_SUP_W) * cost + self.CALL_SUP_W * p_sup)
        return cost

    def _p_hold_faced(self, bidder, q) -> float:
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
        prior, min_face = prior_info if prior_info else (None, 1)
        best_bet, best_loss = None, float("inf")
        cand = []
        pcall_cache = {}
        judge = self._judge(ctx)
        n_live = len(ctx.round_players) if ctx.round_players else 0
        bait_w = self.HU_BAIT_WEIGHT if n_live == 2 else self.BAIT_WEIGHT

        for qty in range(q_lo, q_hi + 1):
            faces = range(min_face, 7) if qty == (prior.quantity if prior else qty) else range(2, 7)
            for face in faces:
                if prior is not None and not (
                    qty > prior.quantity or (qty == prior.quantity and face > prior.face)
                ):
                    continue
                eff_wilds = wilds and (face != 1)
                p_hold = self._p_bid_hold(ctx, qty, face, hand, total, eff_wilds)
                bet = Bet(qty, face, self.name)
                ck = (qty, self._p_hit(face, eff_wilds), eff_wilds)
                p_call = pcall_cache.get(ck)
                if p_call is None:
                    p_call = self._p_any_call(ctx, qty, face, total, eff_wilds)
                    pcall_cache[ck] = p_call
                loss = p_call * ((1.0 - p_hold) - bait_w * p_hold)
                if self.SQUEEZE_WEIGHT:
                    sq = 1.0 - self._best_reraise_pub(qty, face, total, eff_wilds)
                    loss -= self.SQUEEZE_WEIGHT * sq * (1.0 - p_call)
                cand.append((loss, bet, p_hold, p_call))
                if loss < best_loss - 1e-12:
                    best_bet, best_loss = bet, loss

        counts = ctx.stats.dice_counts if ctx.stats else {}
        behind = False
        if counts:
            alive = sum(1 for v in counts.values() if v > 0)
            behind = total > 0 and alive > 0 and len(hand) * alive < total

        can_poison = (
            len(hand) >= self.POISON_MIN_DICE
            and n_live > 2
            and self._poison_pays(judge)
            and (not self.FIRST_BID_POISON_ONLY or self._our_round_bids == 0)
        )

        if behind:
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
        elif can_poison:
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
        if judge is None:
            return True
        fit = self._pgfit.get(judge)
        if fit is None or fit[2] < self.POGATE_MIN:
            return True
        coef, se, _n = fit
        return not (coef < 0.0 and se > 0.0 and coef / se < self.POGATE_Z)

    def _judge(self, ctx):
        players = ctx.round_players
        if players and len(players) > 1 and self.name in players:
            return players[(players.index(self.name) + 1) % len(players)]
        return None

    def _best_reraise(self, qty, face, total, wilds) -> tuple[int, int, float]:
        min_face = 2 if wilds else 1
        options = [(qty + 1, min_face)]
        if face < 6:
            options.append((qty, face + 1))
        q2, f2 = max(options, key=lambda bf: self._p_holds_public(bf[0], bf[1], total, wilds))
        return q2, f2, self._p_holds_public(q2, f2, total, wilds)

    def _best_reraise_pub(self, qty, face, total, wilds) -> float:
        return self._best_reraise(qty, face, total, wilds)[2]

    def _seat_order(self, ctx) -> list:
        players = ctx.round_players
        if players and self.name in players and len(players) > 1:
            idx = players.index(self.name)
            return [players[(idx + 1 + i) % len(players)] for i in range(len(players) - 1)]
        return []

    # ── Online Learning from Completed Rounds ─────────────────────────────────

    def _learn(self, ctx) -> None:
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

    # ── Live Tendency & Support Posterior Update ──────────────────────────────

    def _tend_shift(self, player: str, mode: str, d_j: int) -> float:
        """Signed expected support shift (in dice) for this player in `mode`."""
        s = self._tend.get((player, mode))
        if s is None or s[1] < 2.0:
            return 0.0
        mean_per_die = s[0] / (s[1] + self.TEND_SHRINK)
        return max(-0.25 * d_j, min(0.35 * d_j, mean_per_die * d_j))

    def _apply_conservation(
        self, sup: list[float], face: int, delta: float, d_j: int, wild: bool
    ) -> None:
        """Redistribute a fraction of `delta` across non-bid faces."""
        if abs(delta) < 1e-6 or not self.TEND_CONSERVE:
            return
        other_faces = [g for g in range(2 if wild else 1, 7) if g != face]
        if not other_faces:
            return
        adj = -self.TEND_CONSERVE * delta / len(other_faces)
        for g in other_faces:
            sup[g] = min(float(d_j), max(0.0, sup[g] + adj))

    def _update_held(self, ctx, hand, total) -> None:
        bets = ctx.bet_history
        key = (bets[-1]["game"], bets[-1]["round"]) if len(bets) else None
        if key != self._held_key or len(ctx.outcomes) != self._held_outcomes:
            self._held_key = key
            self._held_outcomes = len(ctx.outcomes)
            self._held = {}
            self._sup = {}
            self._sup_sig = {}
            self._supcache.clear()
            self._our_round_bids = 0
            self._prior_pre_sup = None
            self._prior_revisit = False
            self._held_seen = len(bets)
            while (
                self._held_seen > 0
                and (bets[self._held_seen - 1]["game"], bets[self._held_seen - 1]["round"]) == key
            ):
                self._held_seen -= 1
            self._held_start = self._held_seen

        stats = ctx.stats
        counts = stats.dice_counts if stats else {}
        n_alive = sum(1 for v in counts.values() if v > 0) if counts else 0

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

        wild = not any(bets[j]["bet"].face == 1 for j in range(self._held_start, self._held_seen))
        prev = None
        if self._held_seen > 0:
            e0 = bets[self._held_seen - 1]
            if (e0["game"], e0["round"]) == key:
                prev = e0

        last_idx = len(bets) - 1
        for i in range(self._held_seen, len(bets)):
            e = bets[i]
            if (e["game"], e["round"]) != key:
                continue
            player, bet = e["player"], e["bet"]
            if player == self.name:
                self._our_round_bids += 1
            if bet.face == 1:
                wild = False
            d_j = counts.get(player, 0)
            if player != self.name and d_j:
                p_hit = self._p_hit(bet.face, wild)
                unif = d_j * p_hit
                est = est_for(player)
                implied = bet.quantity - (total - d_j) * p_hit
                est[bet.face] = min(float(d_j), max(est[bet.face], implied))
                faces = self._sup_sig.setdefault(player, set())
                revisit = bet.face in faces
                faces.add(bet.face)

                is_hi_d = d_j >= 3 and (n_alive == 0 or d_j * n_alive >= total)
                sup = sup_for(player)
                if i == last_idx:
                    self._prior_pre_sup = sup[bet.face] if prev is not None else None
                    self._prior_revisit = revisit

                if prev is None:
                    # Opening bid of the round
                    mode = "open_hi" if is_hi_d else "open_lo"
                    self._tend_events.append((key, player, mode, d_j, bet.face, wild))
                    shift = self._tend_shift(player, mode, d_j)
                    base_open = min(float(d_j), max(0.0, unif + shift))
                    if implied > 0.5 and shift >= -0.05 * d_j:
                        rel = self._rel_for(player, "open")
                        new_val = min(
                            float(d_j), max(base_open, 0.85 * implied * rel + 0.3 * shift)
                        )
                        self._rel_events.append((key, player, "open", implied, bet.face, wild))
                    else:
                        new_val = base_open
                    delta = new_val - sup[bet.face]
                    sup[bet.face] = new_val
                    self._apply_conservation(sup, bet.face, delta, d_j, wild)
                else:
                    q0, f0 = prev["bet"].quantity, prev["bet"].face
                    if bet.quantity > q0:
                        cls = "qty"
                    elif bet.quantity == q0 and bet.face > f0:
                        cls = "f6" if bet.face == 6 else "f_lo"
                    else:
                        cls = None
                    if cls:
                        w = (
                            self.SUP_W_QTY
                            if cls == "qty"
                            else (self.SUP_W_F6 if cls == "f6" else self.SUP_W_FLO)
                        )
                        if implied > 0.5:
                            rel = self._rel_for(player, cls)
                            raw_val = w * implied * rel
                            if cls != "f6":
                                mode = "cheap_hi" if is_hi_d else "cheap_lo"
                                shift = self._tend_shift(player, mode, d_j)
                                if shift > 0.0:
                                    raw_val = max(unif + 0.5 * shift, raw_val)
                            new_val = min(float(d_j), raw_val)
                            delta = new_val - sup[bet.face]
                            sup[bet.face] = new_val
                            self._apply_conservation(sup, bet.face, delta, d_j, wild)
                            self._rel_events.append((key, player, cls, implied, bet.face, wild))
                        elif cls != "f6":
                            # Cheap raise: use learned face-choice tendency (honest vs poison)
                            mode = "cheap_hi" if is_hi_d else "cheap_lo"
                            self._tend_events.append((key, player, mode, d_j, bet.face, wild))
                            shift = self._tend_shift(player, mode, d_j)
                            new_val = min(float(d_j), max(0.0, unif + shift))
                            delta = new_val - sup[bet.face]
                            sup[bet.face] = new_val
                            self._apply_conservation(sup, bet.face, delta, d_j, wild)

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
                            sup[bet.face] = min(float(d_j), sup[bet.face] + self.SUP_REV)
            prev = e
        self._held_seen = len(bets)

    def _held_floor(self, player, face) -> int:
        est = self._held.get(player)
        return int(est[face]) if est is not None else 0

    def _rel_score(self, player, cls, implied, actual) -> None:
        s = self._rel.setdefault((player, cls), [0.0, 0.0])
        s[0] += min(3.0, actual / implied)
        s[1] += 1.0
        if s[1] > 240.0:
            s[0] *= 0.5
            s[1] *= 0.5

    def _rel_for(self, player, cls) -> float:
        s = self._rel.get((player, cls))
        if s is None:
            return 1.0
        r = (s[0] + self.SUP_REL_SHRINK) / (s[1] + self.SUP_REL_SHRINK)
        return min(1.6, max(0.3, r))

    def _tend_score(self, player: str, mode: str, d_j: int, actual: int, p_hit: float) -> None:
        if d_j <= 0:
            return
        excess_per_die = (actual - d_j * p_hit) / d_j
        s = self._tend.setdefault((player, mode), [0.0, 0.0])
        s[0] += excess_per_die
        s[1] += 1.0
        if s[1] > 200.0:
            s[0] *= 0.5
            s[1] *= 0.5

    def _consume_round(self, outcome, round_bets) -> None:
        if not round_bets:
            return
        hands = outcome["hands"]
        total = sum(len(h) for h in hands.values())

        def wild_at(upto):
            return not any(e["bet"].face == 1 for e in round_bets[:upto])

        def claim_at(upto, face, decider):
            unseen = max(1, total - len(hands[decider]))
            return (
                sum(
                    e["bet"].quantity
                    for e in round_bets[:upto]
                    if e["bet"].face == face and e["player"] != decider
                )
                / unseen
            )

        rkey = (outcome["game"], outcome["round"])
        if self._rel_events:
            keep = []
            for k, player, cls, implied, face, w in self._rel_events:
                if k != rkey or player not in hands:
                    if k > rkey:
                        keep.append((k, player, cls, implied, face, w))
                    continue
                self._rel_score(player, cls, implied, self._count(list(hands[player]), face, w))
            self._rel_events = keep

        if self._tend_events:
            keep_t = []
            for k, player, mode, d_j, face, w in self._tend_events:
                if k != rkey or player not in hands:
                    if k > rkey:
                        keep_t.append((k, player, mode, d_j, face, w))
                    continue
                actual = self._count(list(hands[player]), face, w)
                self._tend_score(player, mode, len(hands[player]), actual, self._p_hit(face, w))
            self._tend_events = keep_t

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
        last = len(round_bets) - 1
        for i, e in enumerate(round_bets):
            bidder = e["player"]
            if bidder == self.name or bidder not in hands:
                continue
            judge = round_bets[i + 1]["player"] if i < last else outcome["challenger"]
            if judge not in hands:
                continue
            b = e["bet"]
            w = wild_at(i + 1)
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
        best, best_ll = None, float("-inf")
        taus = [0.10 + 0.025 * i for i in range(19)]
        for tau in taus:
            for s in (0.02, 0.05, 0.10):
                ll = 0.0
                for p, called in labels:
                    pc = Retep._sig((tau - p) / s)
                    pc = min(1.0 - 1e-9, max(1e-9, pc))
                    ll += log(pc) if called else log(1.0 - pc)
                if ll > best_ll:
                    best, best_ll = (tau, s), ll
        return best

    @staticmethod
    def _mle_tau(labels, slope) -> float:
        best_tau, best_ll = None, float("-inf")
        for tau in [0.10 + 0.025 * i for i in range(19)]:
            ll = 0.0
            for p, called in labels:
                pc = Retep._sig((tau - p) / slope)
                pc = min(1.0 - 1e-9, max(1e-9, pc))
                ll += log(pc) if called else log(1.0 - pc)
            if ll > best_ll:
                best_tau, best_ll = tau, ll
        return best_tau

    def _fit_tau(self, player) -> None:
        labels = self._labels.get(player)
        if not labels or len(labels) < self.TAU_FIT_MIN:
            return
        last = self._fit_n.get(player, 0)
        if len(labels) - last < self.TAU_FIT_EVERY:
            return
        self._fit[player] = self._mle([(p, c) for p, c, _d in labels])
        self._fit_n[player] = len(labels)

    def _fit_dice(self, player) -> None:
        labels = self._labels.get(player)
        if not labels:
            return
        n = self._labels_total.get(player) or 0
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
        p = min(1.0 - 1e-9, max(1e-9, p))
        return self._sig(self.CAL_A + self.CAL_B * log(p / (1.0 - p)))

    def _p_any_call(self, ctx, qty, face, total, wilds) -> float:
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
        own = self._count(hand, face, wilds)
        need = qty - own
        if need <= 0:
            return 1.0
        unseen = total - len(hand)
        if unseen <= 0:
            return 0.0
        return self._binom_sf(unseen, self._p_hit(face, wilds), need)

    def _sup_suffix(self, ctx, face, total, wilds, hand_len) -> list[float]:
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
        own = self._count(hand, face, wilds)
        need = qty - own
        if need <= 0:
            return 1.0
        suffix = self._sup_suffix(ctx, face, total, wilds, len(hand))
        if need >= len(suffix):
            return 0.0
        return min(1.0, suffix[need])

    def _p_holds_public(self, qty, face, total, wilds) -> float:
        if qty > total:
            return 0.0
        p_hit = 2 / 6 if (wilds and face != 1) else 1 / 6
        return self._binom_sf(total, p_hit, qty)

    def _binom_sf(self, n, p, k) -> float:
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
