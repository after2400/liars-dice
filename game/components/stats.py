from collections import defaultdict


class GameStats:
    """Incremental per-game statistics for all players. Updated O(1) per bet/outcome.

    Pass as the optional 6th arg to algo() — declare `stats=None` in your signature to opt in.
    All public properties return copies of their internal data — reads are safe; writes are blocked.
    """

    def __init__(self) -> None:
        # Backing stores: per-player bluff behavior
        self._bluff_rate: dict[str, float] = {}
        self._bluff_rate_by_face: dict[str, dict[int, float]] = {}
        self._raw_bluff_rate: dict[str, float] = {}
        self._raw_bluff_rate_by_face: dict[str, dict[int, float]] = {}
        self._challenge_rate: dict[str, float] = {}
        self._challenge_success_rate: dict[str, float] = {}

        # Backing stores: bid tendencies
        self._face_bias: dict[str, dict[int, float]] = {}
        self._bid_increment: dict[str, float] = {}
        self._opening_aggression: dict[str, float] = {}
        self._mean_held_quantity_by_face: dict[str, dict[int, float]] = {}

        # Backing stores: revealed-hand data
        self._revealed_hand_frequency: dict[str, dict[int, float]] = {}
        self._rounds_with_hand: dict[str, int] = {}

        # Backing store: current-round context (reset each round)
        self._current_round_velocity: float = 1.0

        # Internal counters
        self._bluff_counts: dict[str, int] = defaultdict(int)
        self._hold_counts: dict[str, int] = defaultdict(int)
        self._bluff_by_face: dict[str, dict[int, int]] = defaultdict(lambda: defaultdict(int))
        self._hold_by_face: dict[str, dict[int, int]] = defaultdict(lambda: defaultdict(int))
        self._challenge_count: dict[str, int] = defaultdict(int)
        self._challenge_success_count: dict[str, int] = defaultdict(int)
        self._turn_count: dict[str, int] = defaultdict(int)
        self._bid_count: dict[str, int] = defaultdict(int)
        self._face_bid_count: dict[str, dict[int, int]] = defaultdict(lambda: defaultdict(int))
        self._total_increment: dict[str, float] = defaultdict(float)
        self._increment_count: dict[str, int] = defaultdict(int)
        self._opening_qty_sum: dict[str, float] = defaultdict(float)
        self._opening_count: dict[str, int] = defaultdict(int)
        self._held_qty_sum: dict[str, dict[int, float]] = defaultdict(lambda: defaultdict(float))
        self._held_qty_count: dict[str, dict[int, int]] = defaultdict(lambda: defaultdict(int))
        self._revealed_face_sum: dict[str, dict[int, float]] = defaultdict(
            lambda: defaultdict(float)
        )
        self._revealed_dice_count: dict[str, int] = defaultdict(int)
        self._current_round_bets: list[int] = []

    # ── Read-only properties ──────────────────────────────────────────────────

    @property
    def bluff_rate(self) -> dict[str, float]:
        return dict(self._bluff_rate)

    @property
    def bluff_rate_by_face(self) -> dict[str, dict[int, float]]:
        return {k: dict(v) for k, v in self._bluff_rate_by_face.items()}

    @property
    def raw_bluff_rate(self) -> dict[str, float]:
        return dict(self._raw_bluff_rate)

    @property
    def raw_bluff_rate_by_face(self) -> dict[str, dict[int, float]]:
        return {k: dict(v) for k, v in self._raw_bluff_rate_by_face.items()}

    @property
    def challenge_rate(self) -> dict[str, float]:
        return dict(self._challenge_rate)

    @property
    def challenge_success_rate(self) -> dict[str, float]:
        return dict(self._challenge_success_rate)

    @property
    def face_bias(self) -> dict[str, dict[int, float]]:
        return {k: dict(v) for k, v in self._face_bias.items()}

    @property
    def bid_increment(self) -> dict[str, float]:
        return dict(self._bid_increment)

    @property
    def opening_aggression(self) -> dict[str, float]:
        return dict(self._opening_aggression)

    @property
    def mean_held_quantity_by_face(self) -> dict[str, dict[int, float]]:
        return {k: dict(v) for k, v in self._mean_held_quantity_by_face.items()}

    @property
    def revealed_hand_frequency(self) -> dict[str, dict[int, float]]:
        return {k: dict(v) for k, v in self._revealed_hand_frequency.items()}

    @property
    def rounds_with_hand(self) -> dict[str, int]:
        return dict(self._rounds_with_hand)

    @property
    def current_round_velocity(self) -> float:
        return self._current_round_velocity

    # ── Mutation methods (engine-internal only) ───────────────────────────────

    def update_bet(self, bet_entry: dict, is_opening_bid: bool, total_dice: int) -> None:
        """Call after each accepted bid. Updates face_bias, bid_increment, opening_aggression,
        and current_round_velocity. Does NOT update bluff/hold counts (those need outcome data).
        Also updates challenge_rate denominator (each bid counts as a turn for challenge-rate tracking)."""
        player = bet_entry["player"]
        bet = bet_entry["bet"]

        # bid_increment: avg quantity jump for non-opening bids
        if not is_opening_bid and self._current_round_bets:
            self._total_increment[player] += bet.quantity - self._current_round_bets[-1]
            self._increment_count[player] += 1
            self._bid_increment[player] = (
                self._total_increment[player] / self._increment_count[player]
            )

        # current_round_velocity
        self._current_round_bets.append(bet.quantity)
        if len(self._current_round_bets) >= 2:
            diffs = [
                self._current_round_bets[i] - self._current_round_bets[i - 1]
                for i in range(1, len(self._current_round_bets))
            ]
            self._current_round_velocity = sum(diffs) / len(diffs)
        # else: stays 1.0 (neutral) until we have 2+ bets

        # face_bias: fraction of this player's bids on each face
        self._bid_count[player] += 1
        self._face_bid_count[player][bet.face] += 1
        n = self._bid_count[player]
        if player not in self._face_bias:
            self._face_bias[player] = {f: 0.0 for f in range(1, 7)}
        for f in range(1, 7):
            self._face_bias[player][f] = self._face_bid_count[player][f] / n

        # opening_aggression: avg opening qty as fraction of total_dice
        if is_opening_bid:
            self._opening_qty_sum[player] += bet.quantity / total_dice
            self._opening_count[player] += 1
            self._opening_aggression[player] = (
                self._opening_qty_sum[player] / self._opening_count[player]
            )

        # turn count for challenge_rate denominator
        self._turn_count[player] += 1
        challenges = self._challenge_count[player]
        self._challenge_rate[player] = challenges / self._turn_count[player]

    def update_outcome(self, outcome: dict) -> None:
        """Call after each round ends. Updates bluff_rate, bluff_rate_by_face, challenge stats,
        mean_held_quantity_by_face, revealed_hand_frequency, and rounds_with_hand."""
        bidder = outcome["bidder"]
        challenger = outcome["challenger"]
        bet_held = outcome["bet_held"]
        final_bet = outcome["final_bet"]
        hands: dict = outcome.get("hands", {})

        # bluff_rate (Laplace-smoothed)
        if bet_held:
            self._hold_counts[bidder] += 1
            self._hold_by_face[bidder][final_bet.face] += 1
        else:
            self._bluff_counts[bidder] += 1
            self._bluff_by_face[bidder][final_bet.face] += 1

        bluffs = self._bluff_counts[bidder]
        holds = self._hold_counts[bidder]
        self._bluff_rate[bidder] = (bluffs + 1) / (bluffs + holds + 2)

        # bluff_rate_by_face (Laplace-smoothed per face)
        if bidder not in self._bluff_rate_by_face:
            self._bluff_rate_by_face[bidder] = {}
        for f in range(1, 7):
            bf = self._bluff_by_face[bidder][f]
            hf = self._hold_by_face[bidder][f]
            self._bluff_rate_by_face[bidder][f] = (bf + 1) / (bf + hf + 2)

        # raw_bluff_rate: unsmoothed failed / (failed + held); absent until first outcome
        bluffs_raw = self._bluff_counts[bidder]
        holds_raw = self._hold_counts[bidder]
        if bluffs_raw + holds_raw > 0:
            self._raw_bluff_rate[bidder] = bluffs_raw / (bluffs_raw + holds_raw)

        # raw_bluff_rate_by_face: unsmoothed per face; only store face that just changed
        face = final_bet.face
        bf_raw = self._bluff_by_face[bidder][face]
        hf_raw = self._hold_by_face[bidder][face]
        if bf_raw + hf_raw > 0:
            if bidder not in self._raw_bluff_rate_by_face:
                self._raw_bluff_rate_by_face[bidder] = {}
            self._raw_bluff_rate_by_face[bidder][face] = bf_raw / (bf_raw + hf_raw)

        # mean_held_quantity_by_face (only for held bids)
        if bet_held:
            self._held_qty_sum[bidder][final_bet.face] += final_bet.quantity
            self._held_qty_count[bidder][final_bet.face] += 1
            if bidder not in self._mean_held_quantity_by_face:
                self._mean_held_quantity_by_face[bidder] = {}
            self._mean_held_quantity_by_face[bidder][final_bet.face] = (
                self._held_qty_sum[bidder][final_bet.face]
                / self._held_qty_count[bidder][final_bet.face]
            )

        # challenge stats
        self._challenge_count[challenger] += 1
        self._turn_count[challenger] += 1
        if not bet_held:
            self._challenge_success_count[challenger] += 1
        total_ch = self._challenge_count[challenger]
        self._challenge_success_rate[challenger] = (
            self._challenge_success_count[challenger] / total_ch
        )
        self._challenge_rate[challenger] = total_ch / self._turn_count[challenger]

        # revealed_hand_frequency and rounds_with_hand
        for player_name, hand in hands.items():
            self._rounds_with_hand[player_name] = self._rounds_with_hand.get(player_name, 0) + 1
            self._revealed_dice_count[player_name] += len(hand)
            if player_name not in self._revealed_hand_frequency:
                self._revealed_hand_frequency[player_name] = {f: 0.0 for f in range(1, 7)}
            for f in range(1, 7):
                self._revealed_face_sum[player_name][f] += hand.count(f)
                self._revealed_hand_frequency[player_name][f] = (
                    self._revealed_face_sum[player_name][f] / self._revealed_dice_count[player_name]
                )

    def reset_round(self, new_round_num: int) -> None:
        """Call after update_outcome at the end of each round. Clears current-round bet tracking
        so current_round_velocity reflects only the new round's bids."""
        self._current_round_bets = []
        self._current_round_velocity = 1.0
