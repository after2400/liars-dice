from __future__ import annotations

from functools import lru_cache
from math import comb, exp

from game.components.bets import Bet
from game.components.context import GameContext

_DESPERATE = 2  # dice count at or below which a bid is "desperate"


@lru_cache(maxsize=4096)
def _sf_table(n: int, sixths: int) -> tuple[float, ...]:
    """Suffix survival S[k] = P(X >= k) for X ~ Binomial(n, sixths/6).

    Cached per (n, sixths) so every candidate bid in the EV scan costs O(1)
    instead of an O(n) tail sum.
    """
    p = sixths / 6.0
    pmf = [comb(n, k) * (p**k) * ((1 - p) ** (n - k)) for k in range(n + 1)]
    sf = [0.0] * (n + 2)
    for k in range(n, -1, -1):
        sf[k] = sf[k + 1] + pmf[k]
    return tuple(min(1.0, s) for s in sf)


def _sf(n: int, sixths: int, k: int) -> float:
    """P(X >= k) for X ~ Binomial(n, sixths/6)."""
    if k <= 0:
        return 1.0
    if k > n or n <= 0:
        return 0.0
    return _sf_table(n, sixths)[k]


class Oracle:
    """
    She's been expecting you. Don't worry about the vase.

    The Oracle doesn't predict the future — she just runs a complete EV scan
    across every possible bid, including wilds, before the round begins. You
    think you're making a choice. She's already computed the optimal one and
    is halfway through a cookie. She targets whoever leads the table each game
    — not just one bot, but whoever currently has the most to lose.

    Key innovations over the field:
    - Full EV scan for opens including face=1 (wilds) — same range as Merovingian
    - p_call blends the immediate next seat (the only player who can actually
      challenge this bid) with the MAX across all remaining players
    - Exponential p_call decay calibrated per player from observed challenge history
    - Desperation-conditioned bluff rates catch cornered players going all-in
    - Opening-bid inference partitions unseen dice before committing to a bet
    - Credibility ceiling discounts bids above each opponent's honest face range
    - Dynamic targeting: EV bonus when the table leader sits next in rotation
    - Squeeze pricing split between opens (0.50) and raises (0.35) — bids that
      leave the table no safe minimum raise corner opponents into bluffing or
      bad calls, and the opening scan is where that pressure pays most
    - Wild-state-correct challenge-threshold learning (no-wild rounds are scored
      at 1/6, not 2/6)
    - O(1) bid scoring via cached binomial survival tables

    Stack-aware loss pricing, elimination pricing, next-seat p_call blending and
    opening deception are implemented as knobs below but ship disabled — each
    tested flat-to-negative against the live PRM field.
    """

    name = "The Oracle"
    avatar = "dfcgw5cr6/The_Oracle.gif"

    EV_SAFE = 0.3
    EV_WIN_CALL = 0.7
    EV_LOSE_CALL = -1.0

    # Squeeze pricing — the single biggest lever vs the current PRM field.
    # Swept 0.15-0.80 in paired-seed trials: raises peak at 0.35 and opens at
    # 0.50 (0.15 flat cost ~5pp overall win rate; higher than 0.50 declines).
    SIZING_WEIGHT = 0.35  # bonus for terminal raises hard to follow
    SIZING_WEIGHT_OPEN: float | None = 0.50  # opening-scan squeeze; None = SIZING_WEIGHT
    LATE_GAME_AVG_DICE = 3.0  # avg dice/player threshold for late-game bonus
    LATE_GAME_WEIGHT = 0.25  # late-game opening aggression multiplier

    BASE_THRESHOLD = 0.22  # base call-liar threshold
    DESPERATION_SENSITIVITY = 0.3
    FACE_WEIGHT = 0.45  # face-specific bluff rate blend weight
    VELOCITY_SENSITIVITY = 0.02

    CHALLENGE_SLOPE = 3.0  # exponential decay steepness for p_call
    MIN_P_CALL = 0.1

    TARGET_EV_WIN_BONUS = 0.4  # extra EV when table leader sits next in rotation
    CRED_WEIGHT = 2.0  # penalty steepness for bids above opponent's honest ceiling

    # --- Ultimate-mode knobs (0.0 disables each feature) ---

    # Weight on the immediate next seat's calibrated challenge probability vs the
    # max across all remaining players. Only the next seat can actually challenge
    # this bid, but the max is a useful worst case for bids meant to stand.
    P_CALL_NEXT_W = 0.0

    # Scales EV_LOSE_CALL by how short-stacked we are: at 1 die a loss is
    # elimination, at 5 dice it is a flesh wound.
    STACK_LOSS_SCALE = 0.0

    # Extra EV for winning a challenge against a one-die opponent — the win
    # removes a whole player, not just a die.
    ELIM_WIN_BONUS = 0.0

    # Opening deception: EV bonus per die of support the rational-inverter
    # opponents would NOT infer from this open (sandbagging their reads).
    DECEPTION_WEIGHT = 0.0

    def __init__(self) -> None:
        self._bh_idx = 0
        self._oc_idx = 0
        self._round_key: tuple[int, int] | None = None
        self._game_key: int | None = None
        self._wilds_active = True
        self._last_bid_dice: dict[tuple[int, int], tuple[str, int]] = {}

        self._desperate: dict[str, list[int]] = {}
        self._comfortable: dict[str, list[int]] = {}

        self._ct_sum: dict[str, float] = {}
        self._ct_count: dict[str, int] = {}

        self._bluff_history_seen = 0
        self._bluff_outcomes_seen = 0
        self._bluff_round_keys: list[tuple[int, int]] = []
        self._bluff_opens: dict[tuple[int, int], dict] = {}
        self._bluff_sum: dict[str, float] = {}
        self._bluff_count: dict[str, int] = {}
        self._no_wilds_rounds: set[tuple[int, int]] = set()

    def _sync(self, ctx: GameContext) -> None:
        bh = ctx.bet_history
        oc = ctx.outcomes

        n = len(bh)
        for i in range(self._bh_idx, n):
            e = bh[i]
            if e["game"] != self._game_key:
                self._game_key = e["game"]
            rk = (e["game"], e["round"])
            if rk != self._round_key:
                self._round_key = rk
                self._wilds_active = e["bet"].face != 1
            self._last_bid_dice[rk] = (e["player"], e["dice_count"])
        self._bh_idx = n

        # Populate _no_wilds_rounds before scoring outcomes so historical
        # challenge thresholds use the correct per-round wild state.
        self._update_bluff_obs(ctx)

        m = len(oc)
        for j in range(self._oc_idx, m):
            o = oc[j]
            rk = (o["game"], o["round"])
            fb = o.get("final_bet")
            challenger = o.get("challenger")
            hands = o.get("hands", {})
            if fb and challenger and hands:
                total = sum(len(h) for h in hands.values())
                wilds = rk not in self._no_wilds_rounds
                pp = self._ph_pub(fb.face, fb.quantity, total, wilds)
                self._ct_sum[challenger] = self._ct_sum.get(challenger, 0.0) + pp
                self._ct_count[challenger] = self._ct_count.get(challenger, 0) + 1

            last = self._last_bid_dice.get(rk)
            if last and last[0] == o.get("bidder"):
                bidder, dice_count = last
                bucket = self._desperate if dice_count <= _DESPERATE else self._comfortable
                counts = bucket.setdefault(bidder, [0, 0])
                if o["bet_held"]:
                    counts[1] += 1
                else:
                    counts[0] += 1
        self._oc_idx = m

    def _update_bluff_obs(self, ctx: GameContext) -> None:
        history = ctx.bet_history
        outcomes = ctx.outcomes

        for i in range(self._bluff_history_seen, len(history)):
            entry = history[i]
            key = (entry["game"], entry["round"])
            if key not in self._bluff_opens:
                self._bluff_opens[key] = {}
                self._bluff_round_keys.append(key)
            opens = self._bluff_opens[key]
            p = entry["player"]
            if p not in opens:
                opens[p] = entry
            if entry["bet"].face == 1:
                self._no_wilds_rounds.add(key)
        self._bluff_history_seen = len(history)

        limit = min(len(outcomes), len(self._bluff_round_keys))
        for i in range(self._bluff_outcomes_seen, limit):
            outcome = outcomes[i]
            key = self._bluff_round_keys[i]
            hands = outcome.get("hands", {})
            total_r = sum(len(h) for h in hands.values())
            wilds_on = key not in self._no_wilds_rounds

            for p, entry in self._bluff_opens[key].items():
                if p not in hands:
                    continue
                face = entry["bet"].face
                qty = entry["bet"].quantity
                d = entry["dice_count"]
                p_val = 1 / 6 if (face == 1 or not wilds_on) else 2 / 6
                inferred = round(max(0.0, min(float(d), qty - (total_r - d) * p_val)))
                actual = hands[p].count(face) + (
                    hands[p].count(1) if (face != 1 and wilds_on) else 0
                )
                self._bluff_sum[p] = self._bluff_sum.get(p, 0.0) + (
                    1.0 if actual < inferred else 0.0
                )
                self._bluff_count[p] = self._bluff_count.get(p, 0) + 1
        self._bluff_outcomes_seen = limit

    def _opening_bluff_rate(self, player: str) -> float:
        n = self._bluff_count.get(player, 0)
        return 0.0 if n < 3 else self._bluff_sum[player] / n

    def _cond_bluff_rate(self, bidder: str, desperate: bool) -> float | None:
        bucket = self._desperate if desperate else self._comfortable
        counts = bucket.get(bidder)
        if counts is None:
            return None
        b, h = counts
        return (b + 1) / (b + h + 2)

    def _round_opening_bids(self, bh) -> dict[str, tuple[int, float, int]]:
        if not bh or self._round_key is None:
            return {}
        entries = []
        for e in reversed(bh):
            if (e["game"], e["round"]) != self._round_key:
                break
            entries.append(e)
        entries.reverse()

        result: dict[str, tuple[int, float, int]] = {}
        for i, e in enumerate(entries):
            p = e["player"]
            if p == self.name or p in result:
                continue
            face, qty, d = e["bet"].face, e["bet"].quantity, e["dice_count"]
            if i == 0:
                result[p] = (face, float(qty), d)
            else:
                prev = entries[i - 1]["bet"]
                if qty > prev.quantity:
                    min_qty, n_opts = prev.quantity + 1, 5
                else:
                    min_qty, n_opts = prev.quantity, 6 - prev.face
                result[p] = (face, max(0, qty - min_qty) + qty / n_opts, d)
        return result

    def _infer_held(
        self, bf: int, bq: float, d: int, total: int, f: int, wilds: bool, br: float = 0.0
    ) -> tuple[int, int]:
        if bf != f:
            return 0, d
        p = 1 / 6 if (f == 1 or not wilds) else 2 / 6
        inferred = round(max(0.0, min(float(d), bq - (total - d) * p)))
        certain = round(inferred * (1.0 - br))
        return certain, d - certain

    def _ph_pub(self, f: int, q: int, total: int, wilds: bool) -> float:
        sixths = 1 if (f == 1 or not wilds) else 2
        return _sf(total, sixths, q)

    def _prob_holds(
        self,
        f: int,
        q: int,
        hand: list[int],
        total: int,
        wilds: bool,
        ob: dict | None = None,
        br: dict | None = None,
    ) -> float:
        own = hand.count(f) + (hand.count(1) if (wilds and f != 1) else 0)
        if ob:
            certain = own
            accounted = sum(d for _, _, d in ob.values())
            uncertain = total - len(hand) - accounted
            for player, (bface, bqty, d) in ob.items():
                c, u = self._infer_held(
                    bface, bqty, d, total, f, wilds, (br or {}).get(player, 0.0)
                )
                certain += c
                uncertain += u
        else:
            certain, uncertain = own, total - len(hand)

        sixths = 2 if (wilds and f != 1) else 1
        return _sf(uncertain, sixths, q - certain)

    def _mrp(self, q: int, f: int, total: int, wilds: bool) -> float:
        """Probability that the next player can make a survivable minimum raise."""
        low_f = 2 if wilds else 1
        opts = [self._ph_pub(low_f, q + 1, total, wilds)]
        if f < 6:
            opts.append(self._ph_pub(f + 1, q, total, wilds))
        return max(opts)

    def _pc_params(self, ctx: GameContext) -> list[tuple[float, float | None]]:
        """Per-remaining-player (base_rate, learned_mean_threshold) in seat order.

        Computed once per turn; _p_call re-evaluates only the cheap exponential
        per candidate bid.
        """
        players = ctx.round_players
        if not players or self.name not in players:
            return []
        idx = players.index(self.name)
        remaining = [players[(idx + 1 + i) % len(players)] for i in range(len(players) - 1)]
        params: list[tuple[float, float | None]] = []
        cr = ctx.stats.challenge_rate if ctx.stats else {}
        for p in remaining:
            base = max(0.1, cr.get(p, 0.3))
            n = self._ct_count.get(p, 0)
            mt = self._ct_sum[p] / n if n else None
            params.append((base, mt))
        return params

    def _p_call_one(self, base: float, mt: float | None, ph_pub: float) -> float:
        if mt is None:
            return max(self.MIN_P_CALL, min(1.0, min(base * 3, 1.0 - (1.0 - base) * ph_pub)))
        return max(self.MIN_P_CALL, min(1.0, base * exp(-self.CHALLENGE_SLOPE * (ph_pub - mt))))

    def _p_call(self, pc_params: list[tuple[float, float | None]], ph_pub: float) -> float:
        """Challenge probability for a bid with public hold-prob ph_pub.

        Blends the immediate next seat (the only player who can actually challenge
        this bid) with the max across all remaining players (worst case for bids
        that must survive the whole rotation), weighted by P_CALL_NEXT_W.
        """
        if not pc_params:
            return 0.3
        rates = [self._p_call_one(base, mt, ph_pub) for base, mt in pc_params]
        pc_max = max(rates)
        w = self.P_CALL_NEXT_W
        if w <= 0.0:
            return pc_max
        return w * rates[0] + (1.0 - w) * pc_max

    def _effective_threshold(self, prior_bet: Bet, stats, dice_count: int | None) -> float:
        """Call threshold blending desperation-conditioned + face-specific bluff rate + velocity."""
        bidder = prior_bet.player
        desperate = dice_count is not None and dice_count <= _DESPERATE
        cond = self._cond_bluff_rate(bidder, desperate)

        face_bluff = stats.bluff_rate_by_face.get(bidder, {}).get(prior_bet.face) if stats else None
        overall = stats.bluff_rate.get(bidder) if stats else None

        if cond is not None and face_bluff is not None:
            bluff_signal = self.FACE_WEIGHT * face_bluff + (1.0 - self.FACE_WEIGHT) * cond
        elif cond is not None:
            bluff_signal = cond
        elif face_bluff is not None and overall is not None:
            bluff_signal = self.FACE_WEIGHT * face_bluff + (1.0 - self.FACE_WEIGHT) * overall
        elif overall is not None:
            bluff_signal = overall
        else:
            bluff_signal = 0.5

        adj = (bluff_signal - 0.5) * self.DESPERATION_SENSITIVITY
        velocity = stats.current_round_velocity if stats else 1.0
        vel_adj = max(0.0, velocity - 1.0) * self.VELOCITY_SENSITIVITY
        return max(0.10, self.BASE_THRESHOLD + adj + vel_adj)

    def _last_dice_for(self, ctx: GameContext, player: str) -> int | None:
        if self._round_key is None:
            return None
        for e in reversed(ctx.bet_history):
            if (e["game"], e["round"]) != self._round_key:
                break
            if e["player"] == player:
                return e["dice_count"]
        return None

    def _next_player(self, ctx: GameContext) -> str | None:
        players = ctx.round_players
        if not players or self.name not in players:
            return None
        idx = players.index(self.name)
        return players[(idx + 1) % len(players)]

    def _identify_target(self, ctx: GameContext) -> str | None:
        counts = ctx.stats.dice_counts if ctx.stats else {}
        candidates = {p: c for p, c in counts.items() if c > 0}
        if not candidates:
            return None
        leader = max(candidates, key=candidates.__getitem__)
        if leader == self.name:
            others = {p: c for p, c in candidates.items() if p != self.name}
            return max(others, key=others.__getitem__) if others else None
        return leader

    def _credibility(self, bidder: str, face: int, qty: int, total: int, stats) -> float:
        if stats is None:
            return 1.0
        ceiling = stats.mean_held_quantity_by_face.get(bidder, {}).get(face)
        if ceiling is None or qty <= ceiling:
            return 1.0
        excess = qty - ceiling
        return max(0.0, 1.0 - self.CRED_WEIGHT * (excess / max(total, 1)))

    def algo(self, ctx: GameContext) -> Bet | None:
        self._sync(ctx)

        hand = ctx.hand
        prior_bet = ctx.prior_bet
        total = ctx.total_dice
        stats = ctx.stats
        wilds = self._wilds_active

        ob = self._round_opening_bids(ctx.bet_history)
        br = {p: self._opening_bluff_rate(p) for p in self._bluff_count}
        pc_params = self._pc_params(ctx)

        n_players = len(ctx.round_players)
        avg_dice = total / n_players if n_players else total
        late_factor = max(0.0, 1.0 - avg_dice / self.LATE_GAME_AVG_DICE)

        next_p = self._next_player(ctx)
        target = self._identify_target(ctx)
        dice_counts = stats.dice_counts if stats else {}

        # Stack-aware loss: a die lost at 1 die is elimination, not a setback.
        ev_lose = self.EV_LOSE_CALL * (1.0 + self.STACK_LOSS_SCALE * (1.0 - len(hand) / 5.0))
        # Elimination pricing: a failed challenge from a one-die next seat removes them.
        ev_win = self.EV_WIN_CALL + (self.TARGET_EV_WIN_BONUS if next_p == target else 0.0)
        if next_p is not None and dice_counts.get(next_p) == 1:
            ev_win += self.ELIM_WIN_BONUS

        if prior_bet is None:
            # Full EV scan for opening including face=1
            best_ev, best_bet = float("-inf"), Bet(1, 2, self.name)
            d_own = len(hand)
            sizing_open = (
                self.SIZING_WEIGHT if self.SIZING_WEIGHT_OPEN is None else self.SIZING_WEIGHT_OPEN
            )
            for q in range(1, total + 1):
                for f in range(1, 7):
                    w = wilds and f != 1
                    ph = self._prob_holds(f, q, hand, total, w, {}, br)
                    pp = self._ph_pub(f, q, total, w)
                    pc = self._p_call(pc_params, pp)
                    sz = 1.0 - self._mrp(q, f, total, w)
                    ev = (
                        (1.0 - pc) * self.EV_SAFE
                        + pc * ph * ev_win
                        + pc * (1.0 - ph) * ev_lose
                        + late_factor * self.LATE_GAME_WEIGHT * q * ph
                        + sizing_open * sz * ph
                    )
                    if self.DECEPTION_WEIGHT > 0.0:
                        # What a rational inverter reads from this open vs what we hold:
                        # hidden support keeps opponents' inference engines underestimating us.
                        p_inv = 1 / 6 if (f == 1 or not w) else 2 / 6
                        own = hand.count(f) + (hand.count(1) if (w and f != 1) else 0)
                        inferred = round(max(0.0, min(float(d_own), q - (total - d_own) * p_inv)))
                        ev += self.DECEPTION_WEIGHT * max(0, own - inferred)
                    if ev > best_ev:
                        best_ev, best_bet = ev, Bet(q, f, self.name)
            return best_bet

        ph_prior = self._prob_holds(prior_bet.face, prior_bet.quantity, hand, total, wilds, ob, br)
        # Credibility ceiling adjusts EV-of-liar only; threshold uses raw ph_prior
        # so the calibrated BASE_THRESHOLD isn't disrupted.
        ph_cred = ph_prior * self._credibility(
            prior_bet.player, prior_bet.face, prior_bet.quantity, total, stats
        )
        ev_win_liar = self.EV_WIN_CALL
        if dice_counts.get(prior_bet.player) == 1:
            ev_win_liar += self.ELIM_WIN_BONUS
        ev_liar = ph_cred * ev_lose + (1.0 - ph_cred) * ev_win_liar

        bidder_dice = self._last_dice_for(ctx, prior_bet.player)
        threshold = self._effective_threshold(prior_bet, stats, bidder_dice)
        if ph_prior < threshold:
            return None

        allowed = range(2, 7) if wilds else range(1, 7)
        pq, pf = prior_bet.quantity, prior_bet.face
        best_ev, best_bet = float("-inf"), None

        for q in range(pq, total + 1):
            for f in allowed:
                if not (q > pq or (q == pq and f > pf)):
                    continue
                ph = self._prob_holds(f, q, hand, total, wilds, ob, br)
                pp = self._ph_pub(f, q, total, wilds)
                pc = self._p_call(pc_params, pp)
                sz = 1.0 - self._mrp(q, f, total, wilds)
                ev = (
                    (1.0 - pc) * self.EV_SAFE
                    + pc * ph * ev_win
                    + pc * (1.0 - ph) * ev_lose
                    + self.SIZING_WEIGHT * sz * ph
                )
                if ev > best_ev:
                    best_ev, best_bet = ev, Bet(q, f, self.name)

        return best_bet if (best_bet is not None and best_ev > ev_liar) else None
