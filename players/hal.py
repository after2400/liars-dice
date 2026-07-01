from __future__ import annotations

from collections import defaultdict
from math import comb, exp

from game.components.bets import Bet
from game.components.context import GameContext


class Hal:
    """
    HAL 9000 doesn't guess. Every decision is computed: exact probabilities,
    stack-adjusted expected value, and a precise model of what each opponent
    can and cannot hold.

    Each turn, every legal bid and the challenge option is evaluated by expected value:

        EV = (1 - p_call) * EV_SAFE
           + p_call * p_holds * EV_WIN_CALL
           + p_call * (1 - p_holds) * EV_LOSE_CALL

    where EV_LOSE_CALL is further scaled by remaining stack — losing a die at
    one die left is existentially worse than losing one at five.

    p_holds is built in three layers:

    1. Opening-bid partitioning (_round_opening_bids / _infer_held):
       Each opponent's first bid is treated as a noisy signal about their held
       dice. Unseen dice are split into certain matches (inferred from the bid)
       and an uncertain pool modeled as binomial. This shifts p_holds away from
       pure table-level statistics toward a hand-informed estimate.

    2. Personalized face probability (_face_p / revealed_hand_frequency):
       Per-opponent face frequencies from revealed hands are blended into the
       base rate (1/6 or 2/6 with wilds), weighted by how many rounds of data
       exist. Hal knows if you consistently roll high on face 4.

    3. Bidder signals:
       Short-stacked bidders (1-2 dice) get a downward p_holds adjustment —
       desperation bluffing is a real tell. Chronic bluffers (high raw_bluff_rate)
       get an additional discount proportional to their deviation from baseline.

    p_call uses per-player challenge threshold learning: Hal tracks the public
    hold-probability at every challenge, builds a per-player mean threshold, and
    scales p_call via sigmoid around that threshold. Wilds state is tracked
    per-round so historical probabilities are computed correctly.

    Bid selection searches all valid (qty, face) pairs with early termination
    once p_holds drops below 1%, and augments EV with a squeeze bonus —
    bids that leave opponents fewer easy escape raises score higher.

    I'm afraid I can't let you bluff that, Stewie.
    """

    name = "HAL 9000"

    # EV weights
    EV_SAFE = 0.3
    EV_WIN_CALL = 0.7
    EV_LOSE_CALL = -1.0

    # Loss penalty amplification as stack shrinks.
    # At 1 die:  effective EV_LOSE ≈ -1.64   (each die is precious)
    # At 5 dice: effective EV_LOSE = -1.0     (standard)
    STACK_LOSS_SCALE = 0.8

    # Floor on predicted challenge probability
    MIN_P_CALL = 0.08

    # Sharp challengers (high challenge_success_rate) get a boosted p_call estimate
    SHARP_CHALLENGER_BOOST = 0.30

    # Sigmoid steepness for per-player learned challenge threshold
    CHALLENGE_SLOPE = 3.0

    # Bidder with 1-2 dice remaining is desperate — more likely to bluff.
    # Applied as a direct downward shift to p_holds on their bets.
    DESPERATION_ADJ_1 = 0.10  # 1 die left
    DESPERATION_ADJ_2 = 0.06  # 2 dice left

    # How strongly a bidder's observed bluff rate shifts p_holds.
    # At baseline (bluff_rate=0.33), adj=0. High bluffers reduce p_holds.
    BLUFF_RATE_SENSITIVITY = 0.28

    # Squeeze bonus: reward bids where the next player has few easy escape raises.
    # sz = 1 - max(P(qty+1 of lowest face holds), P(same qty of face+1 holds))
    # High sz = opponent is trapped. Matches Merovingian's validated 0.15 weight.
    SQUEEZE_BONUS = 0.15

    # Late-game opening aggression: bonus scales with bid quantity when avg dice/player
    # is low — squeezes short-stacked opponents who can't sustain quantity raises.
    LATE_GAME_AVG_DICE = 3.0
    LATE_GAME_AGGRESSION = 0.25

    # Personalized adjustment weight: how much revealed_hand_frequency shifts the need.
    REVEAL_ADJ_WEIGHT = 0.6  # 0=ignore, 1=full trust (blended in below)
    REVEAL_TRUST_ROUNDS = 25  # rounds of observed hands before full trust

    # Default challenge rate assumed when we have no data on a player
    DEFAULT_CHALLENGE_RATE = 0.20

    def __init__(self) -> None:
        self._outcomes_seen: int = 0
        self._bh_idx: int = 0
        self._round_key: tuple[int, int] | None = None
        self._current_game: int | None = None
        self._wilds_active: bool = True
        self._dice: dict[str, int] = {}

        # Rounds where a face-1 bid was placed — wilds were disabled that round.
        # Used to correctly compute p_holds_public for historical challenge outcomes.
        self._no_wilds_rounds: set[tuple[int, int]] = set()

        # Per-player mean p_holds_public at their challenge decisions (learned threshold)
        self._ct_sum: dict[str, float] = defaultdict(float)
        self._ct_count: dict[str, int] = defaultdict(int)

    # ------------------------------------------------------------------
    # State sync
    # ------------------------------------------------------------------

    def _sync(self, ctx: GameContext) -> None:
        for i in range(self._bh_idx, len(ctx.bet_history)):
            entry = ctx.bet_history[i]
            if entry["game"] != self._current_game:
                self._current_game = entry["game"]
                self._dice = {}
            self._dice[entry["player"]] = entry["dice_count"]
            key = (entry["game"], entry["round"])
            if entry["bet"].face == 1:
                self._no_wilds_rounds.add(key)
            if key != self._round_key:
                self._round_key = key
                self._wilds_active = entry["bet"].face != 1
            elif entry["bet"].face == 1:
                self._wilds_active = False
        self._bh_idx = len(ctx.bet_history)

        for i in range(self._outcomes_seen, len(ctx.outcomes)):
            outcome = ctx.outcomes[i]
            final_bet = outcome["final_bet"]
            total = sum(len(h) for h in outcome["hands"].values())
            round_key = (outcome.get("game", 0), outcome.get("round", 0))
            wilds = round_key not in self._no_wilds_rounds
            # Temporarily override wilds state to get the correct historical probability
            saved = self._wilds_active
            self._wilds_active = wilds
            p_pub = self._p_holds_public(final_bet.face, final_bet.quantity, total)
            self._wilds_active = saved
            self._ct_sum[outcome["challenger"]] += p_pub
            self._ct_count[outcome["challenger"]] += 1
        self._outcomes_seen = len(ctx.outcomes)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _wilds(self, face: int) -> bool:
        return self._wilds_active and face != 1

    def _stack_factor(self, hand: list[int]) -> float:
        return len(hand) / 5.0

    def _next_player(self, ctx: GameContext) -> str | None:
        players = ctx.round_players
        if not players:
            return None
        try:
            idx = players.index(self.name)
        except ValueError:
            return None
        return players[(idx + 1) % len(players)]

    # ------------------------------------------------------------------
    # Opening bid inference (EvilStewie-style exact partitioning)
    # ------------------------------------------------------------------

    def _round_opening_bids(self, ctx: GameContext) -> dict[str, tuple[int, float, int]]:
        """Per-opponent first bid this round: {player: (face, effective_qty, dice_count)}."""
        history = ctx.bet_history
        if not history or ctx.prior_bet is None:
            return {}
        last = history[-1]
        cur_round, cur_game = last["round"], last["game"]

        round_entries = []
        for entry in reversed(history):
            if entry["game"] != cur_game or entry["round"] != cur_round:
                break
            round_entries.append(entry)
        round_entries.reverse()

        result: dict[str, tuple[int, float, int]] = {}
        for i, entry in enumerate(round_entries):
            player = entry["player"]
            if player == self.name or player in result:
                continue
            face, qty, d = entry["bet"].face, entry["bet"].quantity, entry["dice_count"]
            if i == 0:
                result[player] = (face, float(qty), d)
            else:
                prev = round_entries[i - 1]["bet"]
                if qty > prev.quantity:
                    min_qty = prev.quantity + 1
                    n_options = 5
                else:
                    min_qty = prev.quantity
                    n_options = 6 - prev.face
                effective = max(0, qty - min_qty) + qty / max(1, n_options)
                result[player] = (face, effective, d)
        return result

    def _infer_held(self, bf: int, bq: float, d: int, total: int, face: int) -> tuple[int, int]:
        """Split a bidder's d dice into (certain_matches, uncertain) for face."""
        if bf != face:
            return 0, d
        p = 2 / 6 if self._wilds(face) else 1 / 6
        inferred = round(max(0.0, min(float(d), bq - (total - d) * p)))
        return inferred, d - inferred

    # ------------------------------------------------------------------
    # Probability model
    # ------------------------------------------------------------------

    def _face_p(self, player: str, face: int, ctx: GameContext) -> float:
        """Personalized matching probability for one die from player.

        Blends revealed_hand_frequency toward the base rate, weighted by
        how many rounds of hand data we've seen. Fully trusted at REVEAL_TRUST_ROUNDS.
        """
        rhf = ctx.stats.revealed_hand_frequency
        if player in rhf:
            rounds = ctx.stats.rounds_with_hand.get(player, 0)
            trust = min(1.0, rounds / self.REVEAL_TRUST_ROUNDS)
            if self._wilds(face):
                obs = rhf[player].get(face, 1 / 6) + rhf[player].get(1, 1 / 6)
                base = 2 / 6
            else:
                obs = rhf[player].get(face, 1 / 6)
                base = 1 / 6
            return trust * obs + (1 - trust) * base
        return 2 / 6 if self._wilds(face) else 1 / 6

    def _p_holds(
        self,
        hand: list[int],
        face: int,
        quantity: int,
        total: int,
        ctx: GameContext,
        opening_bids: dict | None = None,
        bidder: str | None = None,
    ) -> float:
        """P(bet holds), combining three layers of information:

        1. Exact opening-bid partitioning (EvilStewie-style) — certain matches + uncertain pool
        2. Revealed-hand personalization — adjusts the effective need using per-player face bias
        3. Bidder signals — desperation (dice count) and observed bluff rate shift the result
        """
        wilds = self._wilds(face)
        own = hand.count(face) + (hand.count(1) if wilds else 0)
        p = 2 / 6 if wilds else 1 / 6

        # -- Layer 1: opening bid partitioning --
        certain = own
        uncertain = 0

        if opening_bids:
            accounted = sum(d for _, _, d in opening_bids.values())
            uncertain += total - len(hand) - accounted
            for bf, bq, d in opening_bids.values():
                c, u = self._infer_held(bf, bq, d, total, face)
                certain += c
                uncertain += u
        else:
            uncertain = total - len(hand)

        # -- Layer 2: personalized need adjustment from revealed_hand_frequency --
        # For players tracked in self._dice but NOT in opening_bids, shift the effective
        # need based on how their observed face frequency deviates from the base rate.
        personal_adj = 0.0
        if ctx.stats.revealed_hand_frequency:
            for player, d in self._dice.items():
                if player == self.name or d <= 0:
                    continue
                if opening_bids and player in opening_bids:
                    continue
                p_personal = self._face_p(player, face, ctx)
                rounds = ctx.stats.rounds_with_hand.get(player, 0)
                trust = min(1.0, rounds / self.REVEAL_TRUST_ROUNDS) * self.REVEAL_ADJ_WEIGHT
                personal_adj += d * (p_personal - p) * trust

        need = quantity - certain - personal_adj
        if need <= 0:
            return 1.0

        need_int = max(0, round(need))
        if need_int > uncertain:
            return 0.0
        if uncertain <= 0:
            return 0.0

        p_holds = sum(
            comb(uncertain, k) * (p**k) * ((1 - p) ** (uncertain - k))
            for k in range(need_int, uncertain + 1)
        )

        # -- Layer 3: bidder signals (work from round 1) --
        if bidder is not None:
            # Desperation: short-stacked bidders bluff more out of necessity
            bidder_dice = self._dice.get(bidder, 5)
            if bidder_dice == 1:
                p_holds -= self.DESPERATION_ADJ_1
            elif bidder_dice == 2:
                p_holds -= self.DESPERATION_ADJ_2

            # Observed bluff rate: chronic bluffers have less trustworthy bids
            raw = ctx.stats.raw_bluff_rate
            if bidder in raw:
                bluff_rate = raw[bidder]
                p_holds -= (bluff_rate - 0.33) * self.BLUFF_RATE_SENSITIVITY

        return max(0.0, min(1.0, p_holds))

    def _p_holds_public(self, face: int, quantity: int, total: int) -> float:
        """P(bet holds) from the table's perspective — no private information."""
        p = 2 / 6 if self._wilds(face) else 1 / 6
        if quantity <= 0:
            return 1.0
        if quantity > total:
            return 0.0
        return sum(
            comb(total, k) * (p**k) * ((1 - p) ** (total - k)) for k in range(quantity, total + 1)
        )

    # ------------------------------------------------------------------
    # Challenge probability
    # ------------------------------------------------------------------

    def _p_call_one(self, player: str, p_holds_pub: float, ctx: GameContext) -> float:
        base = ctx.stats.challenge_rate.get(player, self.DEFAULT_CHALLENGE_RATE)
        success = ctx.stats.challenge_success_rate.get(player, 0.5)
        base = min(1.0, base + max(0.0, success - 0.5) * self.SHARP_CHALLENGER_BOOST)

        n = self._ct_count.get(player, 0)
        if not n:
            p_call = 1.0 - (1.0 - base) * p_holds_pub
        else:
            mean_threshold = self._ct_sum[player] / n
            scale = exp(-self.CHALLENGE_SLOPE * (p_holds_pub - mean_threshold))
            p_call = base * scale

        return max(self.MIN_P_CALL, min(1.0, p_call))

    def _p_call(self, next_p: str | None, p_holds_pub: float, ctx: GameContext) -> float:
        """Probability the next player challenges.

        Only the immediate next player can directly challenge our bid — players
        further down only see it if everyone before them raises instead.
        """
        if next_p is None:
            return self.DEFAULT_CHALLENGE_RATE
        return self._p_call_one(next_p, p_holds_pub, ctx)

    # ------------------------------------------------------------------
    # Squeeze factor
    # ------------------------------------------------------------------

    def _squeeze(self, face: int, qty: int, total: int) -> float:
        """How trapped is the next player? 1 = no easy escape, 0 = many easy outs.

        Measures how hard it is to make a valid raise: either bump quantity by 1
        (minimum valid face) or bump face at same quantity. Low escape probability
        = high squeeze = good for Hal.
        """
        face_min = 2 if self._wilds_active else 1
        opts = [self._p_holds_public(face_min, qty + 1, total)]
        if face < 6:
            opts.append(self._p_holds_public(face + 1, qty, total))
        return 1.0 - max(opts)

    # ------------------------------------------------------------------
    # Stack-adjusted EV
    # ------------------------------------------------------------------

    def _ev_bid(self, p_holds: float, p_call: float, stack: float) -> float:
        ev_lose = self.EV_LOSE_CALL * (1.0 + self.STACK_LOSS_SCALE * (1.0 - stack))
        return (
            (1 - p_call) * self.EV_SAFE
            + p_call * p_holds * self.EV_WIN_CALL
            + p_call * (1 - p_holds) * ev_lose
        )

    def _ev_call(self, p_holds: float, stack: float) -> float:
        ev_lose = self.EV_LOSE_CALL * (1.0 + self.STACK_LOSS_SCALE * (1.0 - stack))
        return p_holds * ev_lose + (1 - p_holds) * self.EV_WIN_CALL

    # ------------------------------------------------------------------
    # Pressure scoring
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Main algo (v2)
    # ------------------------------------------------------------------

    def algo(self, ctx: GameContext) -> Bet | None:
        self._sync(ctx)

        hand = ctx.hand
        prior = ctx.prior_bet
        total = ctx.total_dice
        next_p = self._next_player(ctx)
        opening_bids = self._round_opening_bids(ctx)
        stack = self._stack_factor(hand)

        if prior is None:
            self._wilds_active = True
            n_players = len(ctx.round_players) or 1
            avg_dice = total / n_players
            late_factor = max(0.0, 1.0 - avg_dice / self.LATE_GAME_AVG_DICE)
            best_bet, best_score = None, float("-inf")
            for face in range(2, 7):
                for qty in range(1, total + 1):
                    ph = self._p_holds(hand, face, qty, total, ctx, None)
                    # p_holds is monotone-decreasing in qty — once negligible, all higher are too
                    if ph < 0.01:
                        break
                    php = self._p_holds_public(face, qty, total)
                    sz = self._squeeze(face, qty, total)
                    ev = self._ev_bid(ph, self._p_call(next_p, php, ctx), stack)
                    ev += self.SQUEEZE_BONUS * sz * ph
                    ev += late_factor * self.LATE_GAME_AGGRESSION * qty * ph
                    if ev > best_score:
                        best_score, best_bet = ev, Bet(qty, face, self.name)
            return best_bet

        # Hard call floor: if the bet almost certainly fails, call immediately.
        # Don't let EV miscalibration talk us out of an obvious challenge.
        bidder = prior.player
        p_prior = self._p_holds(hand, prior.face, prior.quantity, total, ctx, opening_bids, bidder)
        if p_prior < 0.25:
            return None

        ev_call = self._ev_call(p_prior, stack)

        allowed = range(2, 7) if self._wilds_active else range(1, 7)
        best_raise_ev, best_raise_bet = float("-inf"), None
        for face in allowed:
            for qty in range(1, total + 1):
                if not (qty > prior.quantity or (qty == prior.quantity and face > prior.face)):
                    continue
                ph = self._p_holds(hand, face, qty, total, ctx, opening_bids)
                if ph < 0.01:
                    break
                php = self._p_holds_public(face, qty, total)
                sz = self._squeeze(face, qty, total)
                ev = self._ev_bid(ph, self._p_call(next_p, php, ctx), stack)
                ev += self.SQUEEZE_BONUS * sz * ph
                if ev > best_raise_ev:
                    best_raise_ev, best_raise_bet = ev, Bet(qty, face, self.name)

        if best_raise_bet is None or ev_call >= best_raise_ev:
            return None

        return best_raise_bet
