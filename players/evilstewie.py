import logging
from collections import defaultdict
from math import comb, exp

from game.components.bets import Bet
from game.components.context import GameContext

logger = logging.getLogger(__name__)


class EvilStewie:
    """Insufferable EV-maximizing Liar's Dice bot who has read too many poker textbooks.

    Each turn, EvilStewie refuses to make a move without first consulting a spreadsheet.
    Every legal bid (and the option to call liar) is scored by expected value, then the
    highest-EV action is selected — because winging it is for people without PhDs. EV is:

        EV = p_pass * EV_SAFE
           + p_call * p_holds * EV_WIN_CALL
           + p_call * (1 - p_holds) * EV_LOSE_CALL

    where p_holds is EvilStewie's private estimate of how likely the bid is to survive
    a challenge, and p_call is the probability the next player actually challenges.

    Opponent modeling has two layers (EvilStewie calls this "knowing your enemies";
    his therapist calls it "trust issues"):

    1. Opening-bid inference (_round_opening_bids / _infer_held):
       Each player's first bid this round is treated as a signal about how many matching
       dice they hold. This shifts `p_holds` from pure binomial toward a more informed
       estimate that partitions unseen dice into "likely matches" and "uncertain" pools.
       In practice: EvilStewie judges you by the very first thing you say.

    2. Per-player challenge threshold learning (_update_call_obs / _p_call_conditional):
       EvilStewie tracks the public hold-probability of every bet that gets challenged,
       building a per-player mean threshold. `p_call` is then scaled by how the current
       bid compares to that threshold — bids riskier than a player's typical challenge
       floor get a higher predicted call rate; safer bids get a lower one.
       Translation: EvilStewie remembers exactly how brave you were last time. He has notes.

    State (instance-level, persists across games in a series):
        _outcomes_seen      — watermark into ctx.outcomes for incremental processing
        _ct_sum / _ct_count — running mean of p_holds_public at each player's challenges
    """

    name = "EvilStewie"

    # EV weights for each outcome
    EV_SAFE = 0.3  # bet is followed by another bet
    EV_WIN_CALL = 0.7  # we induce a liar call and it fails (best case) — tunable
    EV_LOSE_CALL = -1.0  # we induce a liar call and it succeeds (worst case)

    # Floor on next-player challenge probability — prevents EV collapsing to 0 when
    # a player has never challenged yet (challenge_rate=0 early in the game)
    MIN_P_CALL = 0.1

    # Steepness of the challenge-probability curve around each player's observed threshold.
    # Higher values = sharper transition from likely-to-call to unlikely-to-call.
    CHALLENGE_SLOPE = 3.0

    # Late-game aggression: when avg dice/player falls below this threshold, opening bids
    # receive a quantity-scaled EV bonus to encourage higher opens. This counters the
    # "squeeze" problem where a conservative open wraps the full table back to EvilStewie
    # with an unsupportable bid. Tuning: LATE_GAME_AVG_DICE sets when it kicks in;
    # LATE_GAME_AGGRESSION sets the bonus per unit of quantity at maximum intensity.
    LATE_GAME_AVG_DICE = 3.0
    LATE_GAME_AGGRESSION = 0.25

    def __init__(self) -> None:
        self._outcomes_seen: int = 0
        # Per-player running stats for challenge threshold (mean p_holds_public at challenge time)
        self._ct_sum: dict[str, float] = defaultdict(float)
        self._ct_count: dict[str, int] = defaultdict(int)
        # Per-player opening-bid bluff propensity (fraction of opens where they bluffed)
        self._bluff_outcomes_seen: int = 0
        self._bluff_sum: dict[str, float] = defaultdict(float)
        self._bluff_count: dict[str, int] = defaultdict(int)
        # Incremental index for bluff tracking — rebuilt entry-by-entry as history grows
        self._bluff_history_seen: int = 0
        self._bluff_round_keys: list[tuple[int, int]] = []  # ordered (game, round) pairs
        self._bluff_opens: dict[
            tuple[int, int], dict[str, dict]
        ] = {}  # (game,round)->player->entry
        self._no_wilds_rounds: set[tuple[int, int]] = (
            set()
        )  # rounds where any face=1 bet was placed

    def _wilds_active(self, ctx: GameContext) -> bool:
        """Wilds are off for the whole round once any bet on 1s has been placed.

        Uses the _no_wilds_rounds cache populated incrementally by _update_bluff_obs,
        which must be called before this method each turn.
        """
        history = ctx.bet_history
        if not history or ctx.prior_bet is None:
            return True
        key = (history[-1]["game"], history[-1]["round"])
        return key not in self._no_wilds_rounds

    def _round_opening_bids(self, ctx: GameContext) -> dict[str, tuple[int, float, int]]:
        """Returns {player: (bid_face, effective_qty, dice_count)} for each other player's first bid this round.

        The true opener (first bid of the round) gets full qty credit — no prior constraint.

        Subsequent bids are constrained by the prior, so we credit only:
            effective_qty = qty_excess + bid_qty / num_face_options
        where qty_excess is how much they bid above the minimum required for that face,
        and bid_qty / num_face_options is the face-commitment signal: they chose one face
        out of N valid options, so they get 1/N of the qty as a free signal.

        num_face_options:
          - Higher qty raise (bid_qty > prior_qty): any of 5 faces valid (2–6 with wilds) → N=5
          - Same qty, higher face (bid_qty == prior_qty): only faces prior_face+1..6 valid → N=6-prior_face
        """
        history = ctx.bet_history
        if not history or ctx.prior_bet is None:
            return {}
        current_round = history[-1]["round"]
        current_game = history[-1]["game"]
        round_entries = []
        for entry in reversed(history):
            if entry["game"] != current_game or entry["round"] != current_round:
                break
            round_entries.append(entry)
        round_entries.reverse()

        result: dict[str, tuple[int, float, int]] = {}
        for i, entry in enumerate(round_entries):
            player = entry["player"]
            if player == self.name or player in result:
                continue
            face = entry["bet"].face
            qty = entry["bet"].quantity
            d = entry["dice_count"]

            if i == 0:
                result[player] = (face, float(qty), d)
            else:
                prior_bet = round_entries[i - 1]["bet"]
                if qty > prior_bet.quantity:
                    # Higher-qty raise: could have bid any of 5 faces (2–6 with wilds)
                    min_qty = prior_bet.quantity + 1
                    num_face_options = 5
                else:
                    # Same-qty raise: only faces prior_face+1..6 were valid
                    min_qty = prior_bet.quantity
                    num_face_options = 6 - prior_bet.face

                qty_excess = max(0, qty - min_qty)
                effective_qty = qty_excess + qty / num_face_options
                result[player] = (face, effective_qty, d)

        return result

    def _infer_held(
        self,
        bid_face: int,
        bid_qty: float,
        d: int,
        total_dice: int,
        face: int,
        wilds: bool,
        bluff_rate: float = 0.0,
    ) -> tuple[int, int]:
        """Infer how many dice matching `face` a player holds given their opening bid.

        Under rational no-bluffing, a player opens with:
            bid_qty ≈ own_matches + (total_dice - d) * p

        Inverting: own_matches ≈ bid_qty - (total_dice - d) * p

        `bluff_rate` discounts the inferred count: a known bluffer's signal is trusted
        proportionally less, shifting dice from `certain` back into `uncertain`.

        Returns (certain, uncertain):
          certain  — inferred matching dice from this player (treated as guaranteed)
          uncertain — their remaining dice (modeled at base rate via binomial)
        """
        if bid_face != face:
            return 0, d

        p = 1 / 6 if (face == 1 or not wilds) else 2 / 6
        expected_from_others = (total_dice - d) * p
        inferred = round(max(0.0, min(float(d), bid_qty - expected_from_others)))
        certain = round(inferred * (1.0 - bluff_rate))
        return certain, d - certain

    def _p_holds(
        self,
        hand: list[int],
        face: int,
        qty: int,
        total_dice: int,
        wilds: bool,
        opening_bids: dict[str, tuple[int, float, int]] | None = None,
    ) -> float:
        """Probability the bid holds, incorporating opponent bid information.

        Splits unseen dice into:
          certain  — inferred matching dice from rational opener analysis
          uncertain — remaining dice modeled as binomial at base rate p
        """
        own = hand.count(face)
        if face != 1 and wilds:
            own += hand.count(1)

        certain = own
        uncertain = 0

        if opening_bids:
            accounted = sum(d for _, _, d in opening_bids.values())
            uncertain += total_dice - len(hand) - accounted  # dice from players with no opening bid
            for player, (bid_face, bid_qty, d) in opening_bids.items():
                c, u = self._infer_held(
                    bid_face, bid_qty, d, total_dice, face, wilds, self._bluff_rate(player)
                )
                certain += c
                uncertain += u
        else:
            uncertain = total_dice - len(hand)

        p = 1 / 6 if (face == 1 or not wilds) else 2 / 6
        need = qty - certain
        if need <= 0:
            return 1.0
        if need > uncertain:
            return 0.0
        return sum(
            comb(uncertain, k) * (p**k) * ((1 - p) ** (uncertain - k))
            for k in range(need, uncertain + 1)
        )

    def _p_holds_public(self, face: int, qty: int, total_dice: int, wilds: bool) -> float:
        """P(bid holds) from an opponent's perspective — all dice treated as unknown.

        Used to scale how likely the next player is to call liar: higher/rarer bids
        look suspicious from outside and attract more challenges.
        """
        p = 1 / 6 if (face == 1 or not wilds) else 2 / 6
        if qty <= 0:
            return 1.0
        if qty > total_dice:
            return 0.0
        return sum(
            comb(total_dice, k) * (p**k) * ((1 - p) ** (total_dice - k))
            for k in range(qty, total_dice + 1)
        )

    def _p_call(self, ctx: GameContext) -> float:
        """Probability the next player calls liar, estimated from their challenge_rate."""
        players = ctx.round_players
        if not players:
            return 0.3
        try:
            idx = players.index(self.name)
        except ValueError:
            return 0.3
        next_player = players[(idx + 1) % len(players)]
        return max(self.MIN_P_CALL, ctx.stats.challenge_rate.get(next_player, 0.3))

    def _ev_bid(self, p_holds: float, p_call: float) -> float:
        """
        EV = p_pass  * EV_SAFE
           + p_call  * p_holds     * EV_WIN_CALL   (liar call fails — challenger loses die)
           + p_call  * (1-p_holds) * EV_LOSE_CALL  (liar call succeeds — we lose die)
        """
        p_pass = 1.0 - p_call
        return (
            p_pass * self.EV_SAFE
            + p_call * p_holds * self.EV_WIN_CALL
            + p_call * (1.0 - p_holds) * self.EV_LOSE_CALL
        )

    def _next_player(self, ctx: GameContext) -> str | None:
        """Return the name of the player who acts immediately after EvilStewie this round."""
        players = ctx.round_players
        if not players:
            return None
        try:
            idx = players.index(self.name)
        except ValueError:
            return None
        return players[(idx + 1) % len(players)]

    def _update_call_obs(self, ctx: GameContext) -> None:
        """Process new outcomes to record each challenger's p_holds_public at challenge time.

        Wilds state is not tracked per-round — passing wilds=True is consistent across all
        observations, so the learned threshold self-calibrates regardless.
        """
        outcomes = ctx.outcomes
        for i in range(self._outcomes_seen, len(outcomes)):
            outcome = outcomes[i]
            final_bet = outcome["final_bet"]
            total_dice = sum(len(h) for h in outcome["hands"].values())
            p_holds_pub = self._p_holds_public(
                final_bet.face, final_bet.quantity, total_dice, wilds=True
            )
            challenger = outcome["challenger"]
            self._ct_sum[challenger] += p_holds_pub
            self._ct_count[challenger] += 1
        self._outcomes_seen = len(outcomes)

    def _bluff_rate(self, player: str) -> float:
        """Estimated fraction of opening bids where this player bluffed.

        Returns 0 until at least 3 observations to avoid overreacting to noise.
        """
        n = self._bluff_count.get(player, 0)
        if n < 3:
            return 0.0
        return self._bluff_sum[player] / n

    def _update_bluff_obs(self, ctx: GameContext) -> None:
        """Update per-player opening-bid bluff propensity from newly completed rounds.

        Maintains an incremental index (_bluff_opens, _bluff_round_keys) so each
        history entry and each outcome is processed exactly once — O(new entries)
        per call rather than O(outcomes × history).

        Wilds are always active at round open, so p = 2/6 for face > 1, 1/6 for face == 1.
        """
        outcomes = ctx.outcomes
        history = ctx.bet_history

        # Step 1: extend the index with any new history entries
        for entry in history[self._bluff_history_seen :]:
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

        # Step 2: score any newly completed rounds against revealed hands
        limit = min(len(outcomes), len(self._bluff_round_keys))
        for i in range(self._bluff_outcomes_seen, limit):
            outcome = outcomes[i]
            key = self._bluff_round_keys[i]
            hands = outcome["hands"]
            total_dice = sum(len(h) for h in hands.values())
            wilds_on = key not in self._no_wilds_rounds

            for p, entry in self._bluff_opens[key].items():
                if p not in hands:
                    continue
                face = entry["bet"].face
                qty = entry["bet"].quantity
                d = entry["dice_count"]

                # Inferred matches under rational no-bluffing assumption
                p_val = 1 / 6 if (face == 1 or not wilds_on) else 2 / 6
                expected_from_others = (total_dice - d) * p_val
                inferred = round(max(0.0, min(float(d), qty - expected_from_others)))

                # Actual matches in revealed hand (wilds count only if active this round)
                actual = hands[p].count(face)
                if face != 1 and wilds_on:
                    actual += hands[p].count(1)

                self._bluff_sum[p] += 1.0 if actual < inferred else 0.0
                self._bluff_count[p] += 1

        self._bluff_outcomes_seen = limit

    def _p_call_conditional(
        self, player: str | None, p_holds_pub: float, base_rate: float
    ) -> float:
        """Estimate p(call) conditioned on this bid's public hold probability.

        Uses the player's observed challenge threshold (mean p_holds_public at challenge time)
        to scale the base_rate. Falls back to the original formula when no data exists.
        """
        n = self._ct_count.get(player, 0) if player else 0
        if not n:
            return 1.0 - (1.0 - base_rate) * p_holds_pub
        mean_threshold = self._ct_sum[player] / n
        scale = exp(-self.CHALLENGE_SLOPE * (p_holds_pub - mean_threshold))
        return max(self.MIN_P_CALL, min(1.0, base_rate * scale))

    def _ev_call_liar(self, p_holds: float) -> float:
        """
        EV of calling liar on the prior bet (certainty — we are the one acting):
          p_holds       * EV_LOSE_CALL  (prior holds — we were wrong, we lose a die)
          (1-p_holds)   * EV_WIN_CALL   (prior fails — bidder loses a die)
        """
        return p_holds * self.EV_LOSE_CALL + (1.0 - p_holds) * self.EV_WIN_CALL

    def algo(self, ctx: GameContext) -> Bet | None:
        """Choose the highest-EV action: place a bid or call liar (return None).

        Opening a round: scores all (qty, face) pairs and returns the best bid.
        Mid-round: scores every legal raise against the EV of calling liar on the
        prior bet, and returns whichever action has the higher expected value.
        """
        self._update_call_obs(ctx)
        self._update_bluff_obs(ctx)

        hand = ctx.hand
        prior = ctx.prior_bet
        total = ctx.total_dice
        p_call = self._p_call(ctx)
        next_p = self._next_player(ctx)
        wilds = self._wilds_active(ctx)
        opening_bids = self._round_opening_bids(ctx)
        if prior is None:
            # Late-game aggression: bonus scales with quantity when avg dice/player is low.
            # Prevents EvilStewie from opening too conservatively and getting squeezed when
            # the bet escalates all the way around the table before returning to him.
            n_players = len(ctx.round_players)
            avg_dice = total / n_players if n_players else total
            late_factor = max(0.0, 1.0 - avg_dice / self.LATE_GAME_AVG_DICE)

            candidates = [(q, f) for q in range(1, total + 1) for f in range(1, 7)]
            scored = sorted(
                (
                    (
                        q,
                        f,
                        ph := self._p_holds(hand, f, q, total, wilds, opening_bids),
                        (
                            pca := self._p_call_conditional(
                                next_p, self._p_holds_public(f, q, total, wilds), p_call
                            )
                        ),
                        self._ev_bid(ph, pca) + late_factor * self.LATE_GAME_AGGRESSION * q,
                    )
                    for q, f in candidates
                ),
                key=lambda x: (x[4], x[0], x[1]),
                reverse=True,
            )
            best_q, best_f, _, _, best_ev = scored[0]
            return Bet(best_q, best_f, self.name)

        # Evaluate calling liar vs every valid raise
        p_prior_holds = self._p_holds(hand, prior.face, prior.quantity, total, wilds, opening_bids)
        ev_liar = self._ev_call_liar(p_prior_holds)

        # Bidding on 1s is only legal if the round was opened on 1s (wilds already off).
        # If wilds are still active, the opening wasn't on 1s, so face=1 is forbidden.
        allowed_faces = range(2, 7) if wilds else range(1, 7)
        candidates = [
            (q, f)
            for q in range(1, total + 1)
            for f in allowed_faces
            if q > prior.quantity or (q == prior.quantity and f > prior.face)
        ]

        scored = sorted(
            (
                (
                    q,
                    f,
                    ph := self._p_holds(hand, f, q, total, wilds, opening_bids),
                    (
                        pca := self._p_call_conditional(
                            next_p, self._p_holds_public(f, q, total, wilds), p_call
                        )
                    ),
                    self._ev_bid(ph, pca),
                )
                for q, f in candidates
            ),
            key=lambda x: (x[4], x[0], x[1]),
            reverse=True,
        )

        if not candidates or ev_liar > scored[0][4]:
            return None

        best_q, best_f, _, _, best_ev = scored[0]
        return Bet(best_q, best_f, self.name)
