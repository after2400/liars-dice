from __future__ import annotations

from collections import defaultdict
from math import comb, exp
from typing import Optional

from game.components.bets import Bet
from game.components.context import GameContext


class Ripley:
    """
    Nuke it from orbit — it's the only way to be sure.

    Ripley doesn't out-think the table, she prices it. Every legal action —
    each possible raise and the option to call liar — gets an expected-value
    score, and she takes the best one. No gut calls, no hero bluffs she can't
    back: just the coldest arithmetic at the table, because in an elimination
    game the only thing that matters is not being the one who bleeds out.

    A bid's EV balances three futures: it passes untouched, it gets called and
    holds (a challenger bleeds a die), or it gets called and fails (she bleeds
    one). Her p(challenged) is taken from the single most trigger-happy player
    left to act — a bid has to survive all of them, not just the next seat —
    calibrated by how risky each opponent's own past challenges have been.

    Two things sharpen her past a plain EV maximizer:

    - The squeeze. A bid that leaves the next player no safe raise is worth extra
      even when nobody calls it — cornering them into a bluff or a bad call
      bleeds their dice without risking hers. Weighted aggressively, it's the
      single biggest driver of her win rate.
    - The credibility ceiling. Every player has a demonstrated honest range: the
      average quantity their bids on a face carried when those bids actually
      held. When a live bid climbs above that ceiling it reeks of a bluff, so
      Ripley discounts its odds and calls sooner — reading each opponent's track
      record, not just the dice.

    She also tracks the wild-dice rule honestly (1s stop being wild the moment a
    round opens on them) and reads opponents' opening bids as signal about what
    they hold.
    """

    name = "Ripley"

    # --- EV weights (swept against the live PRM field) ---
    EV_SAFE = 0.3  # bid passes, next player bids over it
    EV_WIN_CALL = 0.7  # bid is challenged and holds — challenger bleeds a die
    EV_LOSE_CALL = -1.0  # bid is challenged and fails — we bleed a die
    SQUEEZE_WEIGHT = 0.25  # bonus for handing the next player no safe raise
    LATE_AGGRESSION = 0.25  # opening-quantity bonus when the table is short on dice
    LATE_AVG_DICE = 3.0  # avg dice/player below which late-game aggression engages

    # --- Opponent modeling knobs ---
    MIN_P_CALL = 0.1  # floor on any single player's challenge probability
    CHALLENGE_SLOPE = 3.0  # steepness of the call curve around a learned threshold

    # --- Credibility ceiling ---
    # Each player has a demonstrated honest range: the mean quantity their bids
    # on a given face carried when those bids actually held. A prior bid whose
    # quantity sits above that ceiling looks like a bluff, so we discount its
    # hold-probability when deciding whether to call. 0.0 disables.
    # Swept vs the live PRM field; 2.0 was the plateau (~+1 pt over disabled).
    CRED_WEIGHT = 2.0

    def __init__(self) -> None:
        self._outcomes_seen = 0
        # Per-challenger running mean of public hold-prob at their challenge time.
        self._ct_sum: dict[str, float] = defaultdict(float)
        self._ct_count: dict[str, int] = defaultdict(int)
        # Round bookkeeping so historical wild-state is scored correctly.
        self._round_keys: list[tuple[int, int]] = []
        self._seen_rounds: set[tuple[int, int]] = set()
        self._no_wild_rounds: set[tuple[int, int]] = set()
        self._history_seen = 0

    # ── Main ────────────────────────────────────────────────────────────────

    def algo(self, ctx: GameContext) -> Optional[Bet]:
        self._ingest(ctx)

        hand = ctx.hand
        prior = ctx.prior_bet
        total = ctx.total_dice
        wilds = ctx.stats.ones_are_wild if ctx.stats else self._wilds_from_history(ctx)
        opening = self._opening_bids(ctx)

        if prior is None:
            return self._open(ctx, hand, total, wilds, opening)

        # EV of calling liar on the prior bid (we act, so no p_call uncertainty).
        # Discount its hold-probability when it exceeds the bidder's honest ceiling.
        p_prior = self._p_holds(prior.quantity, prior.face, hand, total, wilds, opening)
        p_prior *= self._credibility(prior.player, prior.face, prior.quantity, total, ctx.stats)
        ev_liar = p_prior * self.EV_LOSE_CALL + (1.0 - p_prior) * self.EV_WIN_CALL

        best_bet, best_ev = self._best_bid(ctx, hand, total, wilds, opening)
        if best_bet is None or ev_liar >= best_ev:
            return None
        return best_bet

    # ── Bid selection ─────────────────────────────────────────────────────────

    def _best_bid(self, ctx, hand, total, wilds, opening) -> tuple[Optional[Bet], float]:
        prior = ctx.prior_bet
        faces = range(2, 7) if wilds else range(1, 7)
        pq, pf = (prior.quantity, prior.face)
        best_ev, best_bet = float("-inf"), None
        for q in range(1, total + 1):
            for f in faces:
                if not (q > pq or (q == pq and f > pf)):
                    continue
                ev = self._ev_bid(ctx, q, f, hand, total, wilds, opening)
                if ev > best_ev:
                    best_ev, best_bet = ev, Bet(q, f, self.name)
        return best_bet, best_ev

    def _ev_bid(self, ctx, q, f, hand, total, wilds, opening) -> float:
        p_holds = self._p_holds(q, f, hand, total, wilds, opening)
        p_pub = self._p_holds_public(q, f, total, wilds)
        p_call = self._p_call(ctx, p_pub)
        squeeze = 1.0 - self._best_reraise_pub(q, f, total, wilds)
        return (
            (1.0 - p_call) * self.EV_SAFE
            + p_call * p_holds * self.EV_WIN_CALL
            + p_call * (1.0 - p_holds) * self.EV_LOSE_CALL
            + self.SQUEEZE_WEIGHT * squeeze * p_holds
        )

    def _open(self, ctx, hand, total, wilds, opening) -> Bet:
        n_players = len(ctx.round_players)
        avg_dice = total / n_players if n_players else total
        late = max(0.0, 1.0 - avg_dice / self.LATE_AVG_DICE)
        best_ev, best_bet = float("-inf"), Bet(1, 2, self.name)
        for q in range(1, total + 1):
            for f in range(1, 7):
                p_holds = self._p_holds(q, f, hand, total, wilds, opening)
                p_pub = self._p_holds_public(q, f, total, wilds)
                p_call = self._p_call(ctx, p_pub)
                squeeze = 1.0 - self._best_reraise_pub(q, f, total, wilds)
                ev = (
                    (1.0 - p_call) * self.EV_SAFE
                    + p_call * p_holds * self.EV_WIN_CALL
                    + p_call * (1.0 - p_holds) * self.EV_LOSE_CALL
                    + late * self.LATE_AGGRESSION * q * p_holds
                    + self.SQUEEZE_WEIGHT * squeeze * p_holds
                )
                if ev > best_ev:
                    best_ev, best_bet = ev, Bet(q, f, self.name)
        return best_bet

    # ── Probability ───────────────────────────────────────────────────────────

    def _p_holds(self, q, f, hand, total, wilds, opening) -> float:
        """P(bid holds) from our seat: own dice known, opener bids inform the rest."""
        own = hand.count(f) + (hand.count(1) if (wilds and f != 1) else 0)
        p_hit = 2 / 6 if (wilds and f != 1) else 1 / 6

        if not opening:
            unseen = total - len(hand)
            need = q - own
            if need <= 0:
                return 1.0
            return 0.0 if unseen <= 0 else self._binom_sf(unseen, p_hit, need)

        certain = own
        uncertain = total - len(hand) - sum(d for _, _, d in opening.values())
        for bid_face, bid_qty, d in opening.values():
            if bid_face != f:
                uncertain += d
                continue
            inferred = self._infer_held(bid_face, bid_qty, d, total, f, wilds)
            certain += inferred
            uncertain += d - inferred
        need = q - certain
        if need <= 0:
            return 1.0
        return 0.0 if uncertain <= 0 else self._binom_sf(uncertain, p_hit, need)

    def _infer_held(self, bid_face, bid_qty, d, total, face, wilds) -> int:
        """Rational-opener inversion: matches they likely hold given their bid."""
        if bid_face != face:
            return 0
        p = 1 / 6 if (face == 1 or not wilds) else 2 / 6
        return round(max(0.0, min(float(d), bid_qty - (total - d) * p)))

    def _p_holds_public(self, q, f, total, wilds) -> float:
        """P(bid holds) with every die unknown — the outside view a caller has."""
        p = 2 / 6 if (wilds and f != 1) else 1 / 6
        if q <= 0:
            return 1.0
        return 0.0 if q > total else self._binom_sf(total, p, q)

    def _best_reraise_pub(self, q, f, total, wilds) -> float:
        """Public hold-prob of the next player's best cheap raise over (q, f)."""
        min_face = 2 if wilds else 1
        options = [self._p_holds_public(q + 1, min_face, total, wilds)]
        if f < 6:
            options.append(self._p_holds_public(q, f + 1, total, wilds))
        return max(options)

    def _binom_sf(self, n, p, k) -> float:
        """P(X >= k) for X ~ Binomial(n, p)."""
        if k <= 0:
            return 1.0
        if k > n:
            return 0.0
        return sum(comb(n, i) * (p**i) * ((1 - p) ** (n - i)) for i in range(k, n + 1))

    # ── Opponent modeling ─────────────────────────────────────────────────────

    def _p_call(self, ctx: GameContext, p_pub: float) -> float:
        """Probability the bid is challenged before it returns to us.

        A bid must survive every player left to act, so we take the single most
        trigger-happy of them — the worst case — conditioned on how risky this
        bid looks from the outside.
        """
        players = ctx.round_players
        if not players or self.name not in players:
            return 0.3
        idx = players.index(self.name)
        remaining = [players[(idx + 1 + i) % len(players)] for i in range(len(players) - 1)]
        if not remaining:
            return 0.3
        return max(self._p_call_one(ctx, p, p_pub) for p in remaining)

    def _credibility(self, bidder, face, quantity, total, stats) -> float:
        """Hold-prob multiplier (<=1) for a bid that overshoots the bidder's ceiling.

        `mean_held_quantity_by_face` is the average quantity this bidder carried
        when their bids on `face` actually held — their demonstrated honest range.
        Quantity above that is suspicious; the penalty scales with the overshoot
        as a fraction of the dice in play. No history for the face → no opinion.
        """
        if self.CRED_WEIGHT == 0.0 or stats is None:
            return 1.0
        ceiling = stats.mean_held_quantity_by_face.get(bidder, {}).get(face)
        if ceiling is None:
            return 1.0
        excess = quantity - ceiling
        if excess <= 0:
            return 1.0
        return max(0.0, 1.0 - self.CRED_WEIGHT * excess / max(total, 1))

    def _p_call_one(self, ctx, player, p_pub) -> float:
        base = max(self.MIN_P_CALL, ctx.stats.challenge_rate.get(player, 0.3) if ctx.stats else 0.3)
        n = self._ct_count.get(player, 0)
        if not n:
            return max(self.MIN_P_CALL, min(1.0, base * 3, 1.0 - (1.0 - base) * p_pub))
        threshold = self._ct_sum[player] / n
        scaled = base * exp(-self.CHALLENGE_SLOPE * (p_pub - threshold))
        return max(self.MIN_P_CALL, min(1.0, scaled))

    def _ingest(self, ctx: GameContext) -> None:
        """Incrementally track round wild-state and per-challenger call thresholds."""
        history = ctx.bet_history
        for entry in history[self._history_seen :]:
            key = (entry["game"], entry["round"])
            if key not in self._seen_rounds:
                self._seen_rounds.add(key)
                self._round_keys.append(key)
            if entry["bet"].face == 1:
                self._no_wild_rounds.add(key)
        self._history_seen = len(history)

        outcomes = ctx.outcomes
        have_keys = len(self._round_keys) > 0
        limit = min(len(outcomes), len(self._round_keys)) if have_keys else len(outcomes)
        for i in range(self._outcomes_seen, limit):
            o = outcomes[i]
            final = o["final_bet"]
            total = sum(len(h) for h in o["hands"].values())
            wilds = self._round_keys[i] not in self._no_wild_rounds if have_keys else True
            p_pub = self._p_holds_public(final.quantity, final.face, total, wilds)
            challenger = o["challenger"]
            self._ct_sum[challenger] += p_pub
            self._ct_count[challenger] += 1
        self._outcomes_seen = limit

    def _opening_bids(self, ctx: GameContext) -> dict[str, tuple[int, float, int]]:
        """Each other player's first bid this round as (face, effective_qty, dice)."""
        history = ctx.bet_history
        if not history or ctx.prior_bet is None:
            return {}
        g, r = history[-1]["game"], history[-1]["round"]
        # bet_history accumulates across the whole series, so scan backwards from
        # the end and stop once we leave the current round rather than filtering
        # the entire list every turn.
        round_entries = []
        for e in reversed(history):
            if e["game"] != g or e["round"] != r:
                break
            round_entries.append(e)
        round_entries.reverse()
        result: dict[str, tuple[int, float, int]] = {}
        for i, e in enumerate(round_entries):
            player = e["player"]
            if player == self.name or player in result:
                continue
            face, qty, d = e["bet"].face, e["bet"].quantity, e["dice_count"]
            if i == 0:
                result[player] = (face, float(qty), d)
            else:
                prior = round_entries[i - 1]["bet"]
                if qty > prior.quantity:
                    min_qty, n_faces = prior.quantity + 1, 5
                else:
                    min_qty, n_faces = prior.quantity, 6 - prior.face
                effective = max(0, qty - min_qty) + qty / n_faces
                result[player] = (face, effective, d)
        return result

    def _wilds_from_history(self, ctx: GameContext) -> bool:
        history = ctx.bet_history
        if not history:
            return True
        g, r = history[-1]["game"], history[-1]["round"]
        # Backwards scan: the last entry before the round changes is the opener,
        # whose face determines wild-state. Avoids scanning the whole series.
        opening_face = history[-1]["bet"].face
        for e in reversed(history):
            if e["game"] != g or e["round"] != r:
                break
            opening_face = e["bet"].face
        return opening_face != 1
