from __future__ import annotations

import math
from collections import Counter, defaultdict
from typing import Optional

from game.components.bets import Bet


class Merovingian:
    name = "The Merovingian"
    avatar = "hdyiihba/The_Merovingian.png"

    def __init__(self) -> None:
        self._s1 = 0
        self._s2 = defaultdict(float)
        self._s3 = defaultdict(int)
        self._s4 = 0
        self._s5 = []
        self._s6 = set()
        self._s7 = set()
        self._s8 = None
        self._s9 = []
        self._tbl_cache: dict[tuple[int, float], list[float]] = {}
        self._face_inv_cache: dict[int, tuple] = {}
        self._pt_inv: list[tuple] | None = None

    def algo(self, ctx) -> Optional[Bet]:
        # Per-turn lazy caches: every one MUST be reset here, EXCEPT
        # _tbl_cache. _face_inv_cache/_pt_inv depend on per-turn state
        # (total_dice, hand, round_players, ctx.stats, _s2/_s3), so a
        # surviving entry is a correctness bug, not a stale optimisation.
        # _tbl_cache is the opposite: _build_survival_table(n, p) is a pure
        # function of (n, p), so cached tables never go stale and are kept
        # for the instance's whole lifetime -- in production, one instance
        # is reused across an entire run_series of up to N_GAMES games, so
        # n ranges over the whole [1, total_dice] interval seen across that
        # series, not just one turn. Bounded to ~2 x max_total_dice entries
        # (p takes 2 values): ~90 entries / ~70KB at the PRM/CH production
        # max (_POOL_MAX=9 players, total_dice<=45). That bound comes from
        # tier_capacities' PRM/CH/L1 pooling cap, not a hard limit -- the
        # unpooled DED tier has no such cap, so don't copy this reasoning
        # into a bot that plays DED without rechecking. Add any new
        # per-turn cache to the reset block below; add any new pure,
        # bounded-domain cache alongside _tbl_cache instead.
        self._face_inv_cache = {}
        self._pt_inv = None
        self._u1(ctx)
        h, b, td = ctx.hand, ctx.prior_bet, ctx.total_dice
        wa = self._w1(ctx)
        mc = Counter(h)
        ob = self._o1(ctx)
        if b is None:
            return self._open(ctx, h, mc, td, wa)
        ph = self._p1(b.quantity, b.face, h, mc, td, wa, ob)
        ev_l = ph * -1.0 + (1.0 - ph) * 0.7
        af = range(2, 7) if wa else range(1, 7)
        pq, pf = b.quantity, b.face
        best_ev, best_b = float("-inf"), None
        for q in range(1, td + 1):
            for f in af:
                if q > pq or (q == pq and f > pf):
                    ph2 = self._p1(q, f, h, mc, td, wa, ob)
                    ph_pub = self._pp(f, q, td, wa)
                    pc = self._pt(ctx, ph_pub)
                    sz = 1.0 - self._mrp(q, f, td, wa)
                    ev = (
                        (1.0 - pc) * 0.3
                        + pc * ph2 * 0.7
                        + pc * (1.0 - ph2) * -1.0
                        + 0.15 * sz * ph2
                    )
                    if ev > best_ev:
                        best_ev, best_b = ev, Bet(q, f, self.name)
        return best_b if (best_b and ev_l < best_ev) else None

    def _u1(self, ctx) -> None:
        h = ctx.bet_history
        for e in h[self._s4 :]:
            k = (e["game"], e["round"])
            if k != self._s8:
                self._s8 = k
                self._s9 = []
            self._s9.append(e)
            if k not in self._s6:
                self._s5.append(k)
                self._s6.add(k)
            if e["bet"].face == 1:
                self._s7.add(k)
        self._s4 = len(h)
        os = ctx.outcomes
        ht = len(self._s5) > 0
        lim = min(len(os), len(self._s5)) if ht else len(os)
        for i in range(self._s1, lim):
            o = os[i]
            fb, td = o["final_bet"], sum(len(hx) for hx in o["hands"].values())
            wo = self._s5[i] not in self._s7 if ht else True
            pp = self._pp(fb.face, fb.quantity, td, wo)
            ch = o["challenger"]
            self._s2[ch] += pp
            self._s3[ch] += 1
        self._s1 = lim

    def _p1(self, q, f, h, mc, td, wa, ob) -> float:
        m_mat = mc.get(f, 0) + (mc.get(1, 0) if (wa and f != 1) else 0)
        p_hit = 2 / 6 if (wa and f != 1) else 1 / 6
        if ob:
            inv = self._face_inv_cache.get(f)
            if inv is None:
                cert, unc = m_mat, td - len(h) - sum(d for _, _, d in ob.values())
                for p_id, (bf, bq, bd) in ob.items():
                    if bf != f:
                        unc += bd
                    else:
                        p_f = 1 / 6 if (f == 1 or not wa) else 2 / 6
                        inf = round(max(0.0, min(float(bd), bq - (td - bd) * p_f)))
                        cert += inf
                        unc += bd - inf
                inv = (cert, unc)
                self._face_inv_cache[f] = inv
            cert, unc = inv
            s_n = max(0, q - cert)
            return 1.0 if s_n == 0 else (0.0 if unc <= 0 else self._bs(unc, p_hit, s_n))
        un = td - len(h)
        sn = max(0, q - m_mat)
        return 1.0 if sn == 0 else (0.0 if un == 0 else self._bs(un, p_hit, sn))

    def _pp(self, f, q, td, wa) -> float:
        ph = 2 / 6 if (wa and f != 1) else 1 / 6
        return 1.0 if q <= 0 else (0.0 if q > td else self._bs(td, ph, q))

    def _bs(self, n, p, k) -> float:
        if k > n:
            return 0.0
        if k <= 0:
            return 1.0
        tbl = self._tbl_cache.get((n, p))
        if tbl is None:
            tbl = self._build_survival_table(n, p)
            self._tbl_cache[(n, p)] = tbl
        return tbl[k]

    def _build_survival_table(self, n, p) -> list[float]:
        """S[k] = P(X>=k) for X ~ Binomial(n, p), for k in 0..n, built in one O(n) pass."""
        lp = math.log(p) if p > 0 else -float("inf")
        lq = math.log(1 - p) if p < 1 else -float("inf")
        pmf = [0.0] * (n + 1)
        lpmf = n * lq
        pmf[0] = math.exp(lpmf) if lpmf > -float("inf") else 0.0
        for i in range(1, n + 1):
            lpmf += math.log((n - i + 1) / i) + lp - lq
            pmf[i] = math.exp(lpmf) if lpmf > -float("inf") else 0.0
        tbl = [0.0] * (n + 1)
        running = 0.0
        for k in range(n, -1, -1):
            running += pmf[k]
            tbl[k] = min(1.0, running)
        return tbl

    def _o1(self, ctx) -> dict:
        if not ctx.bet_history or ctx.prior_bet is None:
            return {}
        re = self._s9
        res = {}
        for i, e in enumerate(re):
            p = e["player"]
            if p == self.name or p in res:
                continue
            f, q, d = e["bet"].face, e["bet"].quantity, e["dice_count"]
            if i == 0:
                res[p] = (f, float(q), d)
            else:
                pr = re[i - 1]["bet"]
                mq, nf = (pr.quantity + 1, 5) if q > pr.quantity else (pr.quantity, 6 - pr.face)
                res[p] = (f, max(0, q - mq) + q / nf, d)
        return res

    def _pt(self, ctx, ph_pub: float) -> float:
        inv = self._pt_inv
        if inv is None:
            pl = ctx.round_players
            inv = []
            if pl and self.name in pl:
                idx = pl.index(self.name)
                rem = [pl[(idx + 1 + i) % len(pl)] for i in range(len(pl) - 1)]
                for p in rem:
                    base = max(0.1, (ctx.stats.challenge_rate.get(p, 0.3) if ctx.stats else 0.3))
                    n = self._s3.get(p, 0)
                    mt = (self._s2[p] / n) if n else None
                    inv.append((base, mt))
            self._pt_inv = inv
        if not inv:
            return 0.3
        rs = []
        for base, mt in inv:
            if mt is None:
                rs.append(max(0.1, min(1.0, base * 3, 1.0 - (1.0 - base) * ph_pub)))
            else:
                rs.append(max(0.1, min(1.0, base * math.exp(-3.0 * (ph_pub - mt)))))
        return max(rs)

    def _mrp(self, q, f, td, wa) -> float:
        mf = 2 if wa else 1
        opts = [self._pp(mf, q + 1, td, wa)]
        if f < 6:
            opts.append(self._pp(f + 1, q, td, wa))
        return max(opts)

    def _open(self, ctx, h, mc, td, wa) -> Bet:
        ob = self._o1(ctx)
        np_ = len(ctx.round_players)
        avg = td / np_ if np_ else td
        lf = max(0.0, 1.0 - avg / 3.0)
        be, bb = float("-inf"), Bet(1, 2, self.name)
        for q in range(1, td + 1):
            for f in range(1, 7):
                ph = self._p1(q, f, h, mc, td, wa, ob)
                pp = self._pp(f, q, td, wa)
                pc = self._pt(ctx, pp)
                sz = 1.0 - self._mrp(q, f, td, wa)
                ev = (
                    (1.0 - pc) * 0.3
                    + pc * ph * 0.7
                    + pc * (1.0 - ph) * -1.0
                    + lf * 0.25 * q * ph
                    + 0.15 * sz * ph
                )
                if ev > be:
                    be, bb = ev, Bet(q, f, self.name)
        return bb

    def _w1(self, ctx) -> bool:
        if not ctx.bet_history:
            return True
        return self._s9[0]["bet"].face != 1
