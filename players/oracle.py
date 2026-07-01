from __future__ import annotations

from math import comb, exp

from game.components.bets import Bet
from game.components.context import GameContext

_DESPERATE = 2  # dice count at or below which a bid is "desperate"


class Oracle:
    """
    She's been expecting you. Don't worry about the vase.

    The Oracle doesn't predict the future — she just runs a complete EV scan
    across every possible bid, including wilds, before the round begins. You
    think you're making a choice. She's already computed the optimal one and
    is halfway through a cookie. When The Merovingian sits next in rotation,
    she adds extra incentive to corner him (TARGET_EV_WIN_BONUS), because
    some prophecies you fulfill yourself.

    Key innovations over the field:
    - Full EV scan for opens including face=1 (wilds) — same range as Merovingian
    - p_call is the MAX across ALL remaining players, not just the next seat
    - Exponential p_call decay calibrated per player from observed challenge history
    - Desperation-conditioned bluff rates catch cornered players going all-in
    - Opening-bid inference partitions unseen dice before committing to a bet
    - Merovingian-specific EV boost when he is next in rotation
    """

    name = "The Oracle"

    EV_SAFE = 0.3
    EV_WIN_CALL = 0.7
    EV_LOSE_CALL = -1.0

    SIZING_WEIGHT = 0.15  # bonus for terminal bids hard to follow
    LATE_GAME_AVG_DICE = 3.0  # avg dice/player threshold for late-game bonus
    LATE_GAME_WEIGHT = 0.25  # late-game opening aggression multiplier

    BASE_THRESHOLD = 0.22  # base call-liar threshold
    DESPERATION_SENSITIVITY = 0.3
    FACE_WEIGHT = 0.45  # face-specific bluff rate blend weight
    VELOCITY_SENSITIVITY = 0.02

    CHALLENGE_SLOPE = 3.0  # exponential decay steepness for p_call
    MIN_P_CALL = 0.1

    TARGET_NAME = "The Merovingian"
    TARGET_EV_WIN_BONUS = 0.4  # extra EV reward for trapping Merovingian into a failed call

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

        m = len(oc)
        for j in range(self._oc_idx, m):
            o = oc[j]
            fb = o.get("final_bet")
            challenger = o.get("challenger")
            hands = o.get("hands", {})
            if fb and challenger and hands:
                total = sum(len(h) for h in hands.values())
                pp = self._ph_pub(fb.face, fb.quantity, total, True)
                self._ct_sum[challenger] = self._ct_sum.get(challenger, 0.0) + pp
                self._ct_count[challenger] = self._ct_count.get(challenger, 0) + 1

            rk = (o["game"], o["round"])
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

        self._update_bluff_obs(ctx)

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
        p = 1 / 6 if (f == 1 or not wilds) else 2 / 6
        if q <= 0:
            return 1.0
        if q > total:
            return 0.0
        return sum(comb(total, k) * (p**k) * ((1 - p) ** (total - k)) for k in range(q, total + 1))

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

        p = 2 / 6 if (wilds and f != 1) else 1 / 6
        need = q - certain
        if need <= 0:
            return 1.0
        if need > uncertain:
            return 0.0
        return sum(
            comb(uncertain, k) * (p**k) * ((1 - p) ** (uncertain - k))
            for k in range(need, uncertain + 1)
        )

    def _mrp(self, q: int, f: int, total: int, wilds: bool) -> float:
        """Probability that the next player can make a survivable minimum raise."""
        low_f = 2 if wilds else 1
        opts = [self._ph_pub(low_f, q + 1, total, wilds)]
        if f < 6:
            opts.append(self._ph_pub(f + 1, q, total, wilds))
        return max(opts)

    def _p_call_all(self, ctx: GameContext, ph_pub: float) -> float:
        """Max p_call across all remaining players in rotation."""
        players = ctx.round_players
        if not players or self.name not in players:
            return 0.3
        idx = players.index(self.name)
        remaining = [players[(idx + 1 + i) % len(players)] for i in range(len(players) - 1)]
        if not remaining:
            return 0.3

        rates = []
        for p in remaining:
            base = max(0.1, ctx.stats.challenge_rate.get(p, 0.3) if ctx.stats else 0.3)
            n = self._ct_count.get(p, 0)
            if not n:
                rates.append(
                    max(self.MIN_P_CALL, min(1.0, min(base * 3, 1.0 - (1.0 - base) * ph_pub)))
                )
            else:
                mt = self._ct_sum[p] / n
                rates.append(
                    max(
                        self.MIN_P_CALL, min(1.0, base * exp(-self.CHALLENGE_SLOPE * (ph_pub - mt)))
                    )
                )
        return max(rates)

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

    def algo(self, ctx: GameContext) -> Bet | None:
        self._sync(ctx)

        hand = ctx.hand
        prior_bet = ctx.prior_bet
        total = ctx.total_dice
        stats = ctx.stats
        wilds = self._wilds_active

        ob = self._round_opening_bids(ctx.bet_history)
        br = {p: self._opening_bluff_rate(p) for p in self._bluff_count}

        n_players = len(ctx.round_players)
        avg_dice = total / n_players if n_players else total
        late_factor = max(0.0, 1.0 - avg_dice / self.LATE_GAME_AVG_DICE)

        next_p = self._next_player(ctx)
        ev_win = self.EV_WIN_CALL + (
            self.TARGET_EV_WIN_BONUS if next_p == self.TARGET_NAME else 0.0
        )

        if prior_bet is None:
            # Full EV scan for opening including face=1
            best_ev, best_bet = float("-inf"), Bet(1, 2, self.name)
            for q in range(1, total + 1):
                for f in range(1, 7):
                    w = wilds and f != 1
                    ph = self._prob_holds(f, q, hand, total, w, {}, br)
                    pp = self._ph_pub(f, q, total, w)
                    pc = self._p_call_all(ctx, pp)
                    sz = 1.0 - self._mrp(q, f, total, w)
                    ev = (
                        (1.0 - pc) * self.EV_SAFE
                        + pc * ph * ev_win
                        + pc * (1.0 - ph) * self.EV_LOSE_CALL
                        + late_factor * self.LATE_GAME_WEIGHT * q * ph
                        + self.SIZING_WEIGHT * sz * ph
                    )
                    if ev > best_ev:
                        best_ev, best_bet = ev, Bet(q, f, self.name)
            return best_bet

        ph_prior = self._prob_holds(prior_bet.face, prior_bet.quantity, hand, total, wilds, ob, br)
        ev_liar = ph_prior * self.EV_LOSE_CALL + (1.0 - ph_prior) * self.EV_WIN_CALL

        bidder_dice = self._last_dice_for(ctx, prior_bet.player)
        threshold = self._effective_threshold(prior_bet, stats, bidder_dice)
        if ph_prior < threshold:
            return None

        allowed = range(2, 7) if wilds else range(1, 7)
        pq, pf = prior_bet.quantity, prior_bet.face
        best_ev, best_bet = float("-inf"), None

        for q in range(1, total + 1):
            for f in allowed:
                if not (q > pq or (q == pq and f > pf)):
                    continue
                ph = self._prob_holds(f, q, hand, total, wilds, ob, br)
                pp = self._ph_pub(f, q, total, wilds)
                pc = self._p_call_all(ctx, pp)
                sz = 1.0 - self._mrp(q, f, total, wilds)
                ev = (
                    (1.0 - pc) * self.EV_SAFE
                    + pc * ph * ev_win
                    + pc * (1.0 - ph) * self.EV_LOSE_CALL
                    + self.SIZING_WEIGHT * sz * ph
                )
                if ev > best_ev:
                    best_ev, best_bet = ev, Bet(q, f, self.name)

        return best_bet if (best_bet is not None and best_ev > ev_liar) else None
