from __future__ import annotations

import logging
import random
from math import comb

from game.components.bets import Bet
from game.components.context import GameContext

logger = logging.getLogger(__name__)


class Littlefinger:
    """
    Chaos is a ladder.

    Most sharp bots spend the early game quietly building a baseline: who
    bluffs, who calls, what an honest bid from each seat looks like.
    Littlefinger's job is to make sure that baseline is garbage.

    While the table is fat with dice he plays loud and dishonest — inflated
    opening bids, jump raises on faces he barely holds, the occasional
    opening punt on 1s just to kill the wilds and scramble everyone's math.
    Every observer dutifully records the same lesson: Littlefinger lies.

    Then, as the dice thin out, he settles into opponent-aware expected-value
    play — honest bids priced off the binomial math and the table's observed
    habits. But the table's model of him still says "bluffer", so they keep
    calling his honest bids, and every wrong call costs them a die. He
    doesn't climb the ladder. He lets the table fall off it.

    The chaos probability decays smoothly with the average dice per player:
    capped noise at a fresh table, gone entirely once the endgame arrives. It
    also ramps out across the series itself (POISON_GAMES) — once the
    table's models of him are saturated with lies, there is nothing left to
    poison, and from then on he simply plays the better game.
    """

    name = "Littlefinger"

    # --- Chaos phase (avg dice/player drives the fade) ---
    CHAOS_FULL_DICE = 4.0  # at/above this average, chaos is at maximum
    CHAOS_FADE_DICE = 3.5  # at/below this average, chaos is gone
    CHAOS_MAX = 0.4  # ceiling on p_chaos — caps how loud the loudest tables get
    CHAOS_CALL_FLOOR = 0.25  # even chaos calls liar below this hold-prob
    CHAOS_OPEN_DIV = 3  # open inflation: own count + total//DIV (+0..1)
    POISON_GAMES = 150  # chaos ramps to zero across the first N games of a series

    # --- Settled phase (opponent-aware EV play) ---
    EV_SAFE = 0.75  # our bid passes unchallenged
    EV_WIN_CALL = 0.9  # a challenge resolves in our favor — someone else bleeds
    EV_LOSE_CALL = -1.0  # a challenge resolves against us — we bleed
    CRED_WEIGHT = 3.0  # discount for bids above the bidder's demonstrated honest range
    SQUEEZE_WEIGHT = 0.4  # bonus for leaving the next player no cheap safe raise
    BLEED_WEIGHT = 0.5  # caller-dice weighting: prefer being called by fat stacks

    # --- Poison quality ---
    POISON_PURE = 1.0  # P(a chaos bluff invents a face we hold zero of)

    # --- Heads-up endgame (near-exact play) ---
    ENDGAME_TAU = 0.2  # a rational caller challenges when their-seat hold-prob drops below this

    # --- Re-poison (reputation thermostat) ---
    # Maintenance chaos after the ramp: while the board is still fat with
    # dice (where lying is cheap), if our challenged bids have been holding
    # too often — the table reads us as honest — inject chaos until they
    # don't. Never fires on a thin board: a late-game bluff costs a game.
    RECHAOS_RATE = 0.1  # injected p_chaos floor while trusted (0 = off)
    RECHAOS_THRESHOLD = 0.45  # recent held-rate that reads as "trusted"
    RECHAOS_WINDOW = 60  # challenged bids the honesty estimate looks back over
    RECHAOS_MIN_DICE = 4.5  # only fire at/above this avg dice/player

    def __init__(self) -> None:
        # Our own challenged bids are the table's evidence about us:
        # held reads as honest, failed reads as bluffer.
        self._own: list[float] = []
        self._seen_outcomes = 0

    def algo(self, ctx: GameContext) -> Bet | None:
        hand = ctx.hand
        prior = ctx.prior_bet
        total = ctx.total_dice
        wilds = ctx.stats.ones_are_wild if ctx.stats else True
        self._learn(ctx)

        # Heads-up is where games are decided, and with one opponent every
        # unknown die belongs to them — the math is exact, so play it straight.
        if len(ctx.round_players) == 2:
            return self._endgame(ctx, hand, prior, total, wilds)

        n_players = len(ctx.round_players) or 2
        avg_dice = total / n_players
        p_chaos = min(
            self.CHAOS_MAX,
            (avg_dice - self.CHAOS_FADE_DICE) / (self.CHAOS_FULL_DICE - self.CHAOS_FADE_DICE),
        )
        p_chaos = max(0.0, p_chaos)

        # The poison is for the table's series-long models. Once those are
        # saturated, further chaos only costs dice — ramp it out across the
        # first POISON_GAMES of the series and play straight from then on.
        if self.POISON_GAMES:
            history = ctx.bet_history
            game = history[-1]["game"] if len(history) else 0
            p_chaos *= max(0.0, 1.0 - game / self.POISON_GAMES)

        # Maintenance poison: only while the board is fat (cheap lies) and
        # only when we read as trusted — never on a thin board.
        if self.RECHAOS_RATE and avg_dice >= self.RECHAOS_MIN_DICE:
            own = self._own[-self.RECHAOS_WINDOW :]
            if len(own) >= self.RECHAOS_WINDOW // 2:
                if sum(own) / len(own) > self.RECHAOS_THRESHOLD:
                    p_chaos = max(p_chaos, self.RECHAOS_RATE)

        if prior is None:
            return self._open(hand, total, wilds, p_chaos)
        if random.random() < p_chaos:
            return self._chaos(hand, prior, total, wilds)
        return self._settle(ctx, hand, prior, total, wilds)

    # ── Opening bids ────────────────────────────────────────────────────────

    def _open(self, hand, total, wilds, p_chaos) -> Bet:
        if random.random() < p_chaos:
            # Occasionally punt on 1s just to switch the wilds off early.
            if wilds and random.random() < 0.2:
                return Bet(max(1, hand.count(1) + random.randint(0, 1)), 1, self.name)
            # Loud open: a face we may barely hold, at an inflated quantity.
            face = self._bluff_face(hand, wilds, range(2, 7))
            own = self._count(hand, face, wilds)
            qty = own + max(1, total // self.CHAOS_OPEN_DIV) + random.randint(0, 1)
            return Bet(min(qty, total), face, self.name)
        # Honest open: our best face at exactly what we hold.
        best_face = max(range(2, 7), key=lambda f: self._count(hand, f, wilds))
        return Bet(max(1, self._count(hand, best_face, wilds)), best_face, self.name)

    # ── Chaos phase ─────────────────────────────────────────────────────────

    def _chaos(self, hand, prior, total, wilds) -> Bet | None:
        # Even chaos has limits: don't ride a bid that's plainly dead.
        if self._p_holds(prior.quantity, prior.face, hand, total, wilds) < self.CHAOS_CALL_FLOOR:
            return None

        can_raise_qty = prior.quantity < total
        higher = [f for f in range(prior.face + 1, 7)]

        # Jump the quantity — the preferred chaos move since any face stays legal.
        if can_raise_qty and (not higher or random.random() < 0.6):
            qty = prior.quantity + random.randint(1, min(2, total - prior.quantity))
            if prior.face == 1:
                face = self._bluff_face(hand, wilds, range(1, 7))
            else:
                # Mostly stay on-script, sometimes invent a face we don't hold.
                face = (
                    prior.face
                    if random.random() < 0.6
                    else self._bluff_face(hand, wilds, range(2, 7))
                )
            return Bet(qty, face, self.name)

        # Same quantity, higher face — cheaper noise, face must rise to stay legal.
        if higher:
            return Bet(prior.quantity, self._bluff_face(hand, wilds, higher), self.name)
        return None  # bid is already (total, 6): no legal raise exists

    def _bluff_face(self, hand, wilds, faces):
        """A face to lie about. POISON_PURE biases toward faces we hold zero
        of — the most legible lie once hands are revealed."""
        faces = list(faces)
        if random.random() < self.POISON_PURE:
            zero = [f for f in faces if self._count(hand, f, wilds) == 0]
            if zero:
                return random.choice(zero)
        return random.choice(faces)

    # ── Settled phase ───────────────────────────────────────────────────────

    def _settle(self, ctx, hand, prior, total, wilds) -> Bet | None:
        # EV of calling liar: discounted when the bid overshoots what this
        # bidder has demonstrably carried before (their honest range).
        p_prior = self._p_holds(prior.quantity, prior.face, hand, total, wilds)
        p_prior *= self._credibility(ctx.stats, prior.player, prior.face, prior.quantity, total)
        ev_liar = p_prior * self.EV_LOSE_CALL + (1.0 - p_prior) * self.EV_WIN_CALL

        d_us = len(hand)
        d_trigger = self._trigger_dice(ctx)

        best_bet, best_ev = None, float("-inf")
        min_face = 1 if prior.face == 1 else 2  # never re-open 1s ourselves
        for qty in (prior.quantity, prior.quantity + 1):
            for face in range(min_face, 7):
                if not (qty > prior.quantity or face > prior.face):
                    continue
                p_hold = self._p_holds(qty, face, hand, total, wilds)
                p_call = self._p_call(ctx, self._p_holds_public(qty, face, total, wilds))
                # Even unchallenged, a bid that leaves the next player no
                # cheap safe raise corners them into a bluff or a bad call.
                squeeze = 1.0 - self._best_reraise_pub(qty, face, total, wilds)
                ev = (
                    (1.0 - p_call) * self.EV_SAFE
                    + p_call * p_hold * self.EV_WIN_CALL
                    + p_call * (1.0 - p_hold) * self.EV_LOSE_CALL
                    + self.SQUEEZE_WEIGHT * squeeze * p_hold
                )
                if d_trigger is not None:
                    # When we win a challenge, the caller bleeds — prefer
                    # being called by players with more dice than us.
                    ev += self.BLEED_WEIGHT * p_call * p_hold * (d_trigger - d_us) / 5
                if ev > best_ev:
                    best_bet, best_ev = Bet(qty, face, self.name), ev

        if best_bet is None:
            return None  # bid is already (total, 6): calling is the only move
        if ev_liar >= best_ev:
            return None
        return best_bet

    def _learn(self, ctx) -> None:
        """Record the table's evidence about us from each round's resolution."""
        outcomes = ctx.outcomes
        while self._seen_outcomes < len(outcomes):
            o = outcomes[self._seen_outcomes]
            self._seen_outcomes += 1
            if o["bidder"] == self.name:
                self._own.append(1.0 if o["bet_held"] else 0.0)

    def _dice_counts(self, ctx) -> dict:
        """Current dice per player, reconstructed from this game's outcomes.

        Everyone starts at 5; each outcome's loser drops one. Only players
        still alive appear in round_players, so the counts are exact.
        """
        counts = {p: 5 for p in ctx.round_players}
        history = ctx.bet_history
        if not len(history) or not len(ctx.outcomes):
            return counts
        game = history[-1]["game"]
        i = len(ctx.outcomes) - 1
        while i >= 0 and ctx.outcomes[i]["game"] == game:
            loser = ctx.outcomes[i]["loser"]
            if loser in counts:
                counts[loser] -= 1
            i -= 1
        return counts

    def _trigger_dice(self, ctx):
        """Dice held by the likeliest caller among the players left to act."""
        if not self.BLEED_WEIGHT:
            return None
        players = ctx.round_players
        stats = ctx.stats
        if not players or self.name not in players or stats is None:
            return None
        idx = players.index(self.name)
        remaining = [players[(idx + 1 + i) % len(players)] for i in range(len(players) - 1)]
        if not remaining:
            return None
        trigger = max(remaining, key=lambda p: stats.challenge_rate.get(p, 0.3))
        return self._dice_counts(ctx).get(trigger)

    def _credibility(self, stats, bidder, face, quantity, total) -> float:
        """Hold-prob multiplier (<=1) for a bid above the bidder's honest range.

        `mean_held_quantity_by_face` is the average quantity this bidder carried
        when their bids on `face` actually held. Above that ceiling the bid
        smells like a bluff; the discount scales with the overshoot. No history
        for the face → no opinion.
        """
        if stats is None:
            return 1.0
        ceiling = stats.mean_held_quantity_by_face.get(bidder, {}).get(face)
        if ceiling is None:
            return 1.0
        excess = quantity - ceiling
        if excess <= 0:
            return 1.0
        return max(0.0, 1.0 - self.CRED_WEIGHT * excess / max(total, 1))

    def _p_call(self, ctx, p_pub) -> float:
        """P(our bid is challenged before it comes back around).

        The bid must survive every player left to act, so take the most
        trigger-happy of them (their observed challenge_rate), scaled by how
        suspicious the bid looks from the outside: a publicly-certain bid is
        never called, a publicly-dead one is called at twice the base rate.
        """
        players = ctx.round_players
        stats = ctx.stats
        base = 0.3
        if players and self.name in players:
            idx = players.index(self.name)
            remaining = [players[(idx + 1 + i) % len(players)] for i in range(len(players) - 1)]
            rates = [stats.challenge_rate.get(p, 0.3) for p in remaining] if stats else []
            if rates:
                base = max(rates)
        return min(1.0, max(0.1, base) * 2.0 * (1.0 - p_pub))

    def _p_holds_public(self, qty, face, total, wilds) -> float:
        """P(bid holds) with every die unknown — the outside view a caller has."""
        p_hit = 2 / 6 if (wilds and face != 1) else 1 / 6
        if qty > total:
            return 0.0
        return self._binom_sf(total, p_hit, qty)

    def _best_reraise_pub(self, qty, face, total, wilds) -> float:
        """Public hold-prob of the next player's best cheap raise over (qty, face)."""
        min_face = 2 if wilds else 1
        options = [self._p_holds_public(qty + 1, min_face, total, wilds)]
        if face < 6:
            options.append(self._p_holds_public(qty, face + 1, total, wilds))
        return max(options)

    # ── Heads-up endgame ────────────────────────────────────────────────────

    def _endgame(self, ctx, hand, prior, total, wilds) -> Bet | None:
        """Near-exact play with one opponent left.

        Every die we can't see belongs to the opponent, so hold-probabilities
        are exact. The one remaining unknown is their call decision — modeled
        from the dice: for each hand they could hold, a rational caller
        challenges precisely when the bid looks worse than a coin flip from
        their seat. Summing that over the hand distribution gives an exact
        p_call for any bid we float, replacing the population heuristics that
        are at their noisiest just when the game is on the line.

        (A two-ply minimax over the opponent's best response was built and
        ablated three times — vs the L1 pool, vs the champs, and head-to-head
        on the final config: never better, usually worse. Real opponents
        aren't adversarially optimal, so the pessimistic model just folds
        winning positions. Exact one-ply with an honest response model beats
        it.)
        """
        d_opp = total - len(hand)

        ev_liar = float("-inf")
        if prior is not None:
            p_prior = self._p_holds(prior.quantity, prior.face, hand, total, wilds)
            p_prior *= self._credibility(ctx.stats, prior.player, prior.face, prior.quantity, total)
            ev_liar = p_prior * self.EV_LOSE_CALL + (1.0 - p_prior) * self.EV_WIN_CALL

        best_bet, best_ev = None, float("-inf")
        for qty in range(1, total + 1):
            for face in range(1, 7):
                if prior is not None and not (
                    qty > prior.quantity or (qty == prior.quantity and face > prior.face)
                ):
                    continue
                # Never re-open 1s mid-round unless they're already in play.
                if face == 1 and prior is not None and prior.face != 1:
                    continue
                p_hold = self._p_holds(qty, face, hand, total, wilds)
                p_call = self._p_call_heads_up(qty, face, len(hand), d_opp, wilds)
                ev = (
                    (1.0 - p_call) * self.EV_SAFE
                    + p_call * p_hold * self.EV_WIN_CALL
                    + p_call * (1.0 - p_hold) * self.EV_LOSE_CALL
                )
                if ev > best_ev:
                    best_bet, best_ev = Bet(qty, face, self.name), ev

        if best_bet is None or ev_liar >= best_ev:
            return None
        return best_bet

    def _p_call_heads_up(self, qty, face, d_us, d_opp, wilds) -> float:
        """Exact P(the lone opponent calls) under a rational-caller model.

        The opponent holds k matching dice with probability Binomial(d_opp, p).
        From their seat the bid needs qty - k more matches among our d_us
        dice; they call when that probability drops below ENDGAME_TAU.
        """
        p_hit = 2 / 6 if (wilds and face != 1) else 1 / 6
        p_call = 0.0
        for k in range(d_opp + 1):
            pmf = comb(d_opp, k) * (p_hit**k) * ((1 - p_hit) ** (d_opp - k))
            their_p = self._binom_sf(d_us, p_hit, qty - k)
            if their_p < self.ENDGAME_TAU:
                p_call += pmf
        return p_call

    # ── Probability helpers ─────────────────────────────────────────────────

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

    @staticmethod
    def _binom_sf(n, p, k) -> float:
        """P(X >= k) for X ~ Binomial(n, p)."""
        if k <= 0:
            return 1.0
        if k > n:
            return 0.0
        return sum(comb(n, i) * (p**i) * ((1 - p) ** (n - i)) for i in range(k, n + 1))
