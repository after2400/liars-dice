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

    def algo(self, ctx) -> Optional[Bet]:
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
            cert, unc = m_mat, td - len(h) - sum(d for _, _, d in ob.values())
            for p_id, (bf, bq, bd) in ob.items():
                if bf != f:
                    unc += bd
                else:
                    p_f = 1 / 6 if (f == 1 or not wa) else 2 / 6
                    inf = round(max(0.0, min(float(bd), bq - (td - bd) * p_f)))
                    cert += inf
                    unc += bd - inf
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
        t = 0.0
        lp, lq = (
            math.log(p) if p > 0 else -float("inf"),
            math.log(1 - p) if p < 1 else -float("inf"),
        )
        lpmf = (
            math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1) + k * lp + (n - k) * lq
        )
        for i in range(k, n + 1):
            if i > k:
                lpmf += math.log((n - i + 1) / i) + lp - lq
            t += math.exp(lpmf)
        return min(1.0, t)

    def _o1(self, ctx) -> dict:
        h = ctx.bet_history
        if not h or ctx.prior_bet is None:
            return {}
        cur_r, cur_g = h[-1]["round"], h[-1]["game"]
        re = [e for e in h if e["game"] == cur_g and e["round"] == cur_r]
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
        pl = ctx.round_players
        if not pl or self.name not in pl:
            return 0.3
        idx = pl.index(self.name)
        rem = [pl[(idx + 1 + i) % len(pl)] for i in range(len(pl) - 1)]
        if not rem:
            return 0.3
        rs = []
        for p in rem:
            base = max(0.1, (ctx.stats.challenge_rate.get(p, 0.3) if ctx.stats else 0.3))
            n = self._s3.get(p, 0)
            if not n:
                rs.append(max(0.1, min(1.0, base * 3, 1.0 - (1.0 - base) * ph_pub)))
            else:
                mt = self._s2[p] / n
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
        cg, cr = ctx.bet_history[-1]["game"], ctx.bet_history[-1]["round"]
        for e in ctx.bet_history:
            if e["game"] == cg and e["round"] == cr:
                return e["bet"].face != 1
        return True
