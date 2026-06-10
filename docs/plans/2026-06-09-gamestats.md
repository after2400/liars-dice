# GameStats Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `GameStats` incremental-stats object to the game engine and migrate the four O(n) player algorithms (Eva, Zara, Sloane, Remy) to use it, eliminating per-turn history scans.

**Architecture:** `GameStats` lives in `game/components/stats.py` and is created once per `run_series()` call. It is updated incrementally inside `game_orchestrator()` after each bid and each round outcome. `game_orchestrator()` inspects each player's `algo` signature via `inspect.signature`; players that declare a 6th parameter receive the `stats` object, all others are called with the existing 5-arg signature.

**Tech Stack:** Python 3.11+, `collections.defaultdict`, `inspect`, `uv run pytest`

**IMPORTANT — always use `uv run python` and `uv run pytest`, never bare `python` or `pytest`.**

---

## File Map

| Action | Path                        |
| ------ | --------------------------- |
| Create | `game/components/stats.py`  |
| Modify | `game/components/script.py` |
| Modify | `game/components/series.py` |
| Modify | `players/eva.py`            |
| Modify | `players/zara.py`           |
| Modify | `players/sloane.py`         |
| Modify | `players/remy.py`           |
| Modify | `README.md`                 |
| Create | `tests/test_stats.py`       |
| Modify | `tests/test_main.py`        |

---

## Task 1: GameStats class

**Files:**

- Create: `game/components/stats.py`
- Create: `tests/test_stats.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_stats.py`:

```python
import pytest
from unittest.mock import MagicMock


def _bet(player: str, face: int, quantity: int, game: int = 1, rnd: int = 1) -> dict:
    b = MagicMock()
    b.face = face
    b.quantity = quantity
    return {"game": game, "round": rnd, "player": player, "bet": b}


def _outcome(
    bidder: str,
    challenger: str,
    face: int,
    quantity: int,
    bet_held: bool,
    hands: dict | None = None,
) -> dict:
    fb = MagicMock()
    fb.face = face
    fb.quantity = quantity
    return {
        "game": 1,
        "round": 1,
        "hands": hands or {},
        "final_bet": fb,
        "bidder": bidder,
        "challenger": challenger,
        "bet_held": bet_held,
        "loser": challenger if bet_held else bidder,
    }


# --- bluff_rate ---

def test_bluff_rate_default_before_any_outcome():
    from game.components.stats import GameStats
    stats = GameStats()
    assert stats.bluff_rate.get("Alice", 0.5) == pytest.approx(0.5)


def test_bluff_rate_after_one_bluff():
    from game.components.stats import GameStats
    stats = GameStats()
    stats.update_outcome(_outcome("Alice", "Bruno", 3, 5, bet_held=False))
    # (1 bluff + 1) / (1 + 0 + 2) = 2/3
    assert stats.bluff_rate["Alice"] == pytest.approx(2 / 3)


def test_bluff_rate_after_one_hold():
    from game.components.stats import GameStats
    stats = GameStats()
    stats.update_outcome(_outcome("Alice", "Bruno", 3, 5, bet_held=True))
    # (0 + 1) / (0 + 1 + 2) = 1/3
    assert stats.bluff_rate["Alice"] == pytest.approx(1 / 3)


# --- bluff_rate_by_face ---

def test_bluff_rate_by_face_after_bluff_on_face():
    from game.components.stats import GameStats
    stats = GameStats()
    stats.update_outcome(_outcome("Alice", "Bruno", 3, 5, bet_held=False))
    # face 3: (1+1)/(1+0+2) = 2/3
    assert stats.bluff_rate_by_face["Alice"][3] == pytest.approx(2 / 3)
    # face 2 (no data): (0+1)/(0+0+2) = 0.5
    assert stats.bluff_rate_by_face["Alice"][2] == pytest.approx(0.5)


# --- current_round_velocity ---

def test_velocity_is_neutral_with_one_bet():
    from game.components.stats import GameStats
    stats = GameStats()
    stats.update_bet(_bet("Alice", 3, 5), is_opening_bid=True, total_dice=20)
    assert stats.current_round_velocity == pytest.approx(1.0)


def test_velocity_computed_from_two_bets():
    from game.components.stats import GameStats
    stats = GameStats()
    stats.update_bet(_bet("Alice", 3, 4), is_opening_bid=True, total_dice=20)
    stats.update_bet(_bet("Bruno", 3, 7), is_opening_bid=False, total_dice=20)
    # velocity = (7 - 4) / 1 = 3.0
    assert stats.current_round_velocity == pytest.approx(3.0)


def test_reset_round_restores_neutral_velocity():
    from game.components.stats import GameStats
    stats = GameStats()
    stats.update_bet(_bet("Alice", 3, 4), is_opening_bid=True, total_dice=20)
    stats.update_bet(_bet("Bruno", 3, 9), is_opening_bid=False, total_dice=20)
    stats.reset_round(2)
    assert stats.current_round_velocity == pytest.approx(1.0)


# --- mean_held_quantity_by_face ---

def test_mean_held_quantity_single_outcome():
    from game.components.stats import GameStats
    stats = GameStats()
    stats.update_outcome(_outcome("Alice", "Bruno", 3, 6, bet_held=True))
    assert stats.mean_held_quantity_by_face["Alice"][3] == pytest.approx(6.0)


def test_mean_held_quantity_averages_multiple():
    from game.components.stats import GameStats
    stats = GameStats()
    stats.update_outcome(_outcome("Alice", "Bruno", 3, 4, bet_held=True))
    stats.update_outcome(_outcome("Alice", "Bruno", 3, 8, bet_held=True))
    assert stats.mean_held_quantity_by_face["Alice"][3] == pytest.approx(6.0)


def test_bluff_not_counted_in_mean_held_quantity():
    from game.components.stats import GameStats
    stats = GameStats()
    stats.update_outcome(_outcome("Alice", "Bruno", 3, 10, bet_held=False))
    assert stats.mean_held_quantity_by_face.get("Alice", {}).get(3) is None


# --- revealed_hand_frequency and rounds_with_hand ---

def test_revealed_hand_frequency_single_round():
    from game.components.stats import GameStats
    stats = GameStats()
    hands = {"Alice": [2, 2, 3, 5, 6]}
    stats.update_outcome(_outcome("Alice", "Bruno", 3, 3, bet_held=False, hands=hands))
    assert stats.revealed_hand_frequency["Alice"][2] == pytest.approx(2 / 5)
    assert stats.revealed_hand_frequency["Alice"][3] == pytest.approx(1 / 5)
    assert stats.revealed_hand_frequency["Alice"][4] == pytest.approx(0.0)


def test_rounds_with_hand_counts_all_players_in_hands():
    from game.components.stats import GameStats
    stats = GameStats()
    hands = {"Alice": [1, 2, 3], "Bruno": [4, 5]}
    stats.update_outcome(_outcome("Alice", "Bruno", 3, 2, bet_held=False, hands=hands))
    assert stats.rounds_with_hand["Alice"] == 1
    assert stats.rounds_with_hand["Bruno"] == 1


def test_rounds_with_hand_accumulates_across_rounds():
    from game.components.stats import GameStats
    stats = GameStats()
    hands = {"Alice": [2, 3]}
    stats.update_outcome(_outcome("Alice", "Bruno", 2, 2, bet_held=True, hands=hands))
    stats.update_outcome(_outcome("Alice", "Bruno", 2, 2, bet_held=False, hands=hands))
    assert stats.rounds_with_hand["Alice"] == 2
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_stats.py -v
```

Expected: `ImportError: cannot import name 'GameStats' from 'game.components.stats'` (module doesn't exist yet).

- [ ] **Step 3: Implement `game/components/stats.py`**

```python
from collections import defaultdict


class GameStats:
    """Incremental per-game statistics for all players. Updated O(1) per bet/outcome.

    Pass as the optional 6th arg to algo() — declare `stats=None` in your signature to opt in.
    All public attributes are plain dict or float reads: O(1).
    """

    def __init__(self) -> None:
        # Public: per-player bluff behavior
        self.bluff_rate: dict[str, float] = {}
        self.bluff_rate_by_face: dict[str, dict[int, float]] = {}
        self.challenge_rate: dict[str, float] = {}
        self.challenge_success_rate: dict[str, float] = {}

        # Public: bid tendencies
        self.face_bias: dict[str, dict[int, float]] = {}
        self.bid_increment: dict[str, float] = {}
        self.opening_aggression: dict[str, float] = {}
        self.mean_held_quantity_by_face: dict[str, dict[int, float]] = {}

        # Public: revealed-hand data
        self.revealed_hand_frequency: dict[str, dict[int, float]] = {}
        self.rounds_with_hand: dict[str, int] = {}

        # Public: current-round context (reset each round)
        self.current_round_velocity: float = 1.0

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

    def update_bet(self, bet_entry: dict, is_opening_bid: bool, total_dice: int) -> None:
        """Call after each accepted bid. Updates face_bias, bid_increment, opening_aggression,
        and current_round_velocity. Does NOT update bluff/hold counts (those need outcome data)."""
        player = bet_entry["player"]
        bet = bet_entry["bet"]

        # bid_increment: avg quantity jump for non-opening bids
        if not is_opening_bid and self._current_round_bets:
            self._total_increment[player] += bet.quantity - self._current_round_bets[-1]
            self._increment_count[player] += 1
            self.bid_increment[player] = (
                self._total_increment[player] / self._increment_count[player]
            )

        # current_round_velocity
        self._current_round_bets.append(bet.quantity)
        if len(self._current_round_bets) >= 2:
            diffs = [
                self._current_round_bets[i] - self._current_round_bets[i - 1]
                for i in range(1, len(self._current_round_bets))
            ]
            self.current_round_velocity = sum(diffs) / len(diffs)
        # else: stays 1.0 (neutral) until we have 2+ bets

        # face_bias: fraction of this player's bids on each face
        self._bid_count[player] += 1
        self._face_bid_count[player][bet.face] += 1
        n = self._bid_count[player]
        if player not in self.face_bias:
            self.face_bias[player] = {f: 0.0 for f in range(1, 7)}
        for f in range(1, 7):
            self.face_bias[player][f] = self._face_bid_count[player][f] / n

        # opening_aggression: avg opening qty as fraction of total_dice
        if is_opening_bid:
            self._opening_qty_sum[player] += bet.quantity / total_dice
            self._opening_count[player] += 1
            self.opening_aggression[player] = (
                self._opening_qty_sum[player] / self._opening_count[player]
            )

        # turn count for challenge_rate denominator
        self._turn_count[player] += 1
        challenges = self._challenge_count[player]
        self.challenge_rate[player] = challenges / self._turn_count[player]

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
        self.bluff_rate[bidder] = (bluffs + 1) / (bluffs + holds + 2)

        # bluff_rate_by_face (Laplace-smoothed per face)
        if bidder not in self.bluff_rate_by_face:
            self.bluff_rate_by_face[bidder] = {}
        for f in range(1, 7):
            bf = self._bluff_by_face[bidder][f]
            hf = self._hold_by_face[bidder][f]
            self.bluff_rate_by_face[bidder][f] = (bf + 1) / (bf + hf + 2)

        # mean_held_quantity_by_face (only for held bids)
        if bet_held:
            self._held_qty_sum[bidder][final_bet.face] += final_bet.quantity
            self._held_qty_count[bidder][final_bet.face] += 1
            if bidder not in self.mean_held_quantity_by_face:
                self.mean_held_quantity_by_face[bidder] = {}
            self.mean_held_quantity_by_face[bidder][final_bet.face] = (
                self._held_qty_sum[bidder][final_bet.face]
                / self._held_qty_count[bidder][final_bet.face]
            )

        # challenge stats
        self._challenge_count[challenger] += 1
        self._turn_count[challenger] += 1
        if not bet_held:
            self._challenge_success_count[challenger] += 1
        total_ch = self._challenge_count[challenger]
        self.challenge_success_rate[challenger] = (
            self._challenge_success_count[challenger] / total_ch
        )
        self.challenge_rate[challenger] = total_ch / self._turn_count[challenger]

        # revealed_hand_frequency and rounds_with_hand
        for player_name, hand in hands.items():
            self.rounds_with_hand[player_name] = self.rounds_with_hand.get(player_name, 0) + 1
            self._revealed_dice_count[player_name] += len(hand)
            if player_name not in self.revealed_hand_frequency:
                self.revealed_hand_frequency[player_name] = {f: 0.0 for f in range(1, 7)}
            for f in range(1, 7):
                self._revealed_face_sum[player_name][f] += hand.count(f)
                self.revealed_hand_frequency[player_name][f] = (
                    self._revealed_face_sum[player_name][f]
                    / self._revealed_dice_count[player_name]
                )

    def reset_round(self, new_round_num: int) -> None:
        """Call after update_outcome at the end of each round. Clears current-round bet tracking
        so current_round_velocity reflects only the new round's bids."""
        self._current_round_bets = []
        self.current_round_velocity = 1.0
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_stats.py -v
```

Expected: all 15 tests pass.

- [ ] **Step 5: Run full suite to check for regressions**

```bash
uv run pytest tests/ -v
```

Expected: all 55 existing tests + 15 new = 70 pass.

- [ ] **Step 6: Commit**

```bash
git add game/components/stats.py tests/test_stats.py
git commit -m "feat(game): add GameStats incremental stats class"
```

---

## Task 2: Engine integration

**Files:**

- Modify: `game/components/script.py`
- Modify: `game/components/series.py`
- Modify: `tests/test_main.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_main.py` (append after the last test):

```python
def test_stats_passed_to_six_arg_player(tmp_path):
    """A player declaring a 6th arg receives a non-None GameStats instance."""
    import sys
    from pathlib import Path

    received: list = []

    player_src = textwrap.dedent("""
        from game.components.bets import Bet

        class Spy:
            name = "Spy"
            def algo(self, hand, prior_bet, total_dice, bet_history, outcomes, stats=None):
                from game.components.stats import GameStats
                assert isinstance(stats, GameStats), f"expected GameStats, got {type(stats)}"
                if prior_bet is None:
                    return Bet(1, 2, self.name)
                return None
    """)

    player_dir = tmp_path / "players"
    player_dir.mkdir()
    (player_dir / "spy.py").write_text(player_src)
    (player_dir / "__init__.py").write_text("")

    from game.components.utils import import_player_classes_from_dir
    from game.components.series import run_series

    players = import_player_classes_from_dir(str(player_dir))
    assert len(players) == 1

    # Need a second player so a game can run (≥2 players required)
    class AlwaysBid:
        name = "AlwaysBid"
        def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):
            from game.components.bets import Bet
            if prior_bet is None:
                return Bet(1, 2, self.name)
            return Bet(prior_bet.quantity + 1, prior_bet.face, self.name)

    wins = run_series(players + [AlwaysBid()], n_games=1)
    # If the assertion inside Spy.algo fired, run_series would have raised.
    # Reaching here means stats was a GameStats instance.
    assert set(wins.keys()) == {"Spy", "AlwaysBid"}
```

Also add `import textwrap` near the top of `tests/test_main.py` if not already present.

- [ ] **Step 2: Run to verify it fails**

```bash
uv run pytest tests/test_main.py::test_stats_passed_to_six_arg_player -v
```

Expected: `AssertionError: expected GameStats, got <class 'NoneType'>` (stats is None because engine doesn't pass it yet).

- [ ] **Step 3: Modify `game/components/series.py`**

Replace the entire file with:

```python
import logging

from game.components.stats import GameStats

logger = logging.getLogger(__name__)


def run_series(players: list, n_games: int) -> dict[str, int]:
    """Runs n_games games between the given players and returns win counts.

    Args:
        players: List of player objects, each implementing the algo interface.
        n_games: Number of games to play.

    Returns:
        Dict mapping player name -> number of wins.
    """
    from game.components.script import game_orchestrator

    wins = {type(p).__name__: 0 for p in players}
    bet_history: list[dict] = []
    outcomes: list[dict] = []
    stats = GameStats()

    for game_num in range(1, n_games + 1):
        # Reset file logs so gamelog.log reflects only the current game
        for handler in logging.root.handlers:
            if isinstance(handler, logging.FileHandler):
                handler.stream.seek(0)
                handler.stream.truncate(0)

        winner = game_orchestrator(
            players, game_id=game_num, bet_history=bet_history, outcomes=outcomes, stats=stats
        )
        wins[type(winner).__name__] += 1
        logger.info(f"Game {game_num}/{n_games}: {type(winner).__name__} wins")

    return wins


def format_results(wins: dict[str, int], n_games: int) -> str:
    """Formats series results as a summary table with win-rate bars.

    Args:
        wins: Dict mapping player name -> win count.
        n_games: Total games played (used to compute percentages).

    Returns:
        Formatted string ready to print.
    """
    BAR_WIDTH = 40

    name_w = max(len(n) for n in wins) + 2
    sorted_wins = sorted(wins.items(), key=lambda x: x[1], reverse=True)
    top = sorted_wins[0][1] if sorted_wins else 1

    header = f"  {'Player':<{name_w}}  {'Wins':>5}   {'Win %':>6}   Chart"
    divider = "  " + "-" * (name_w + 5 + 9 + BAR_WIDTH + 5)

    rows = []
    for name, count in sorted_wins:
        pct = count / n_games * 100
        bar_len = round(count / top * BAR_WIDTH) if top else 0
        bar = "█" * bar_len
        rows.append(f"  {name:<{name_w}}  {count:>5}   {pct:>5.1f}%   {bar}")

    lines = [
        f"\n=== Series Results — {n_games} games ===\n",
        header,
        divider,
        *rows,
    ]
    return "\n".join(lines)
```

- [ ] **Step 4: Modify `game/components/script.py`**

Make the following targeted changes:

**4a.** Add `import inspect` after the existing imports at the top:

```python
import inspect
import logging
import random as r

from game.components.bets import Bet, bet_grader, bet_validator
from game.components.utils import FACES
```

**4b.** Change the `game_orchestrator` signature to accept `stats=None`:

```python
def game_orchestrator(
    players: list,
    game_id: int = 1,
    bet_history: list[dict] | None = None,
    outcomes: list[dict] | None = None,
    stats=None,
):
```

**4c.** Add signature inspection immediately after the docstring (before `logger.info("=== New Game ===")`):

```python
    _wants_stats = {
        p: len(inspect.signature(p.algo).parameters) >= 6
        for p in players
    }
    logger.info("=== New Game ===")
```

**4d.** Replace the `player.algo(...)` call block (lines 82–88 in the original) with:

```python
            try:
                if stats is not None and _wants_stats[player]:
                    action = player.algo(
                        hands[player_idx],
                        current_bet,
                        total_dice,
                        bet_history,
                        completed_outcomes,
                        stats,
                    )
                else:
                    action = player.algo(
                        hands[player_idx],
                        current_bet,
                        total_dice,
                        bet_history,
                        completed_outcomes,
                    )
```

**4e.** After `completed_outcomes.append(...)` (inside the liar-call branch), add stats hooks:

```python
                    completed_outcomes.append(
                        {
                            "game": game_id,
                            "round": round_num,
                            "hands": {players[i].name: hands[i] for i in active_list},
                            "final_bet": current_bet,
                            "bidder": players[prev_bidder].name,
                            "challenger": player.name,
                            "bet_held": bet_held,
                            "loser": players[loser].name,
                        }
                    )
                    if stats is not None:
                        stats.update_outcome(completed_outcomes[-1])
                        stats.reset_round(round_num + 1)
```

**4f.** After `bet_history.append(...)` (inside the valid-bid branch), add the bet hook. The append block currently ends at `step += 1`; insert between them:

```python
                    bet_history.append(
                        {
                            "game": game_id,
                            "round": round_num,
                            "player": player.name,
                            "bet": current_bet,
                        }
                    )
                    if stats is not None:
                        stats.update_bet(
                            bet_history[-1],
                            is_opening_bid=(step == 0),
                            total_dice=total_dice,
                        )
                    if current_bet.face == 1 and wilds:
```

- [ ] **Step 5: Run the new test**

```bash
uv run pytest tests/test_main.py::test_stats_passed_to_six_arg_player -v
```

Expected: PASS.

- [ ] **Step 6: Run full suite**

```bash
uv run pytest tests/ -v
```

Expected: 71 tests pass (70 from Task 1 + 1 new).

- [ ] **Step 7: Commit**

```bash
git add game/components/series.py game/components/script.py tests/test_main.py
git commit -m "feat(game): integrate GameStats into engine — pass to 6-arg players"
```

---

## Task 3: Migrate Eva

**Files:**

- Modify: `players/eva.py`

No new tests — the migration is algebraically equivalent. The existing series tests cover correctness.

- [ ] **Step 1: Replace `players/eva.py`**

```python
from math import comb

from game.components.bets import Bet


class Eva:
    """
    Opponent-calibrated strategy. Computes exact binomial probability like Diego,
    but adjusts the liar threshold per opponent based on their historical reliability.
    Known bluffers trigger calls earlier; reliable players get more benefit of the doubt.
    """

    name = "Eva"

    def _prob_bet_holds(self, hand: list, face: int, quantity: int, total_dice: int) -> float:
        own = hand.count(face) + (hand.count(1) if face != 1 else 0)
        unseen = total_dice - len(hand)
        p = 1 / 6 if face == 1 else 2 / 6
        need = quantity - own
        if need <= 0:
            return 1.0
        if need > unseen:
            return 0.0
        return sum(
            comb(unseen, k) * (p**k) * ((1 - p) ** (unseen - k)) for k in range(need, unseen + 1)
        )

    def _reliability(self, player_name: str, outcomes: list) -> float:
        held = sum(1 for o in outcomes if o["bidder"] == player_name and o["bet_held"])
        failed = sum(1 for o in outcomes if o["bidder"] == player_name and not o["bet_held"])
        total = held + failed
        return held / total if total > 0 else 0.5

    def _threshold(self, bluff_rate: float) -> float:
        # Equivalent to original formula with reliability = 1 - bluff_rate:
        # 0.30 - (reliability - 0.5) * 0.30  →  0.30 + (bluff_rate - 0.5) * 0.30
        return 0.30 + (bluff_rate - 0.5) * 0.30

    def algo(
        self,
        hand: list,
        prior_bet: Bet | None,
        total_dice: int,
        bet_history: list[dict],
        outcomes: list[dict],
        stats=None,
    ) -> Bet | None:
        if prior_bet is None:
            best_face = max(range(2, 7), key=lambda f: hand.count(f) + hand.count(1))
            own = hand.count(best_face) + hand.count(1)
            unseen = total_dice - len(hand)
            quantity = max(1, round(own + unseen * (2 / 6) * 0.8))
            return Bet(quantity, best_face, self.name)

        if stats is not None:
            bluff_rate = stats.bluff_rate.get(prior_bet.player, 0.5)
        else:
            bluff_rate = 1 - self._reliability(prior_bet.player, outcomes)

        if self._prob_bet_holds(hand, prior_bet.face, prior_bet.quantity, total_dice) < self._threshold(bluff_rate):
            return None

        own = hand.count(prior_bet.face) + (hand.count(1) if prior_bet.face != 1 else 0)
        if own > 0:
            return Bet(prior_bet.quantity + 1, prior_bet.face, self.name)
        for face in range(prior_bet.face + 1, 7):
            if hand.count(face) + hand.count(1) > 0:
                return Bet(prior_bet.quantity, face, self.name)
        return Bet(prior_bet.quantity + 1, prior_bet.face, self.name)
```

- [ ] **Step 2: Run full suite**

```bash
uv run pytest tests/ -v
```

Expected: 71 tests pass.

- [ ] **Step 3: Commit**

```bash
git add players/eva.py
git commit -m "feat(players): migrate Eva to use GameStats for bluff_rate"
```

---

## Task 4: Migrate Zara

**Files:**

- Modify: `players/zara.py`

- [ ] **Step 1: Replace `players/zara.py`**

```python
from math import comb

from game.components.bets import Bet


class Zara:
    """
    Bayesian opponent-modeling strategy. Computes exact binomial probability like Diego,
    but adjusts the liar threshold per opponent using a Laplace-smoothed bluff rate.
    More robust than Eva's raw ratio on small samples — a single bluff raises the
    threshold less aggressively, and a single hold lowers it less aggressively.
    """

    name = "Zara"

    def _prob_bet_holds(self, hand: list, face: int, quantity: int, total_dice: int) -> float:
        own = hand.count(face) + (hand.count(1) if face != 1 else 0)
        unseen = total_dice - len(hand)
        p = 1 / 6 if face == 1 else 2 / 6
        need = quantity - own
        if need <= 0:
            return 1.0
        if need > unseen:
            return 0.0
        return sum(
            comb(unseen, k) * (p**k) * ((1 - p) ** (unseen - k)) for k in range(need, unseen + 1)
        )

    def _bluff_rate(self, player_name: str, outcomes: list[dict]) -> float:
        bluffs = sum(1 for o in outcomes if o["bidder"] == player_name and not o["bet_held"])
        holds = sum(1 for o in outcomes if o["bidder"] == player_name and o["bet_held"])
        return (bluffs + 1) / (bluffs + holds + 2)

    def _threshold(self, bluff_rate: float) -> float:
        return 0.15 + bluff_rate * 0.30

    def algo(
        self,
        hand: list,
        prior_bet: Bet | None,
        total_dice: int,
        bet_history: list[dict],
        outcomes: list[dict],
        stats=None,
    ) -> Bet | None:
        if prior_bet is None:
            best_face = max(range(2, 7), key=lambda f: hand.count(f) + hand.count(1))
            own = hand.count(best_face) + hand.count(1)
            unseen = total_dice - len(hand)
            quantity = max(1, round(own + unseen * (2 / 6) * 0.75))
            return Bet(quantity, best_face, self.name)

        if stats is not None:
            bluff_rate = stats.bluff_rate.get(prior_bet.player, 0.5)
        else:
            bluff_rate = self._bluff_rate(prior_bet.player, outcomes)

        if self._prob_bet_holds(hand, prior_bet.face, prior_bet.quantity, total_dice) < self._threshold(bluff_rate):
            return None

        own = hand.count(prior_bet.face) + (hand.count(1) if prior_bet.face != 1 else 0)
        if own > 0:
            return Bet(prior_bet.quantity + 1, prior_bet.face, self.name)
        for face in range(prior_bet.face + 1, 7):
            if hand.count(face) + hand.count(1) > 0:
                return Bet(prior_bet.quantity, face, self.name)
        return Bet(prior_bet.quantity + 1, prior_bet.face, self.name)
```

- [ ] **Step 2: Run full suite**

```bash
uv run pytest tests/ -v
```

Expected: 71 tests pass.

- [ ] **Step 3: Commit**

```bash
git add players/zara.py
git commit -m "feat(players): migrate Zara to use GameStats for bluff_rate"
```

---

## Task 5: Migrate Sloane

**Files:**

- Modify: `players/sloane.py`

- [ ] **Step 1: Replace `players/sloane.py`**

```python
from math import comb

from game.components.bets import Bet


class Sloane:
    name = "Sloane"

    def _prob_bet_holds(self, hand: list[int], face: int, quantity: int, total_dice: int) -> float:
        own = hand.count(face) + (hand.count(1) if face != 1 else 0)
        unseen = total_dice - len(hand)
        p = 1 / 6 if face == 1 else 2 / 6
        need = quantity - own
        if need <= 0:
            return 1.0
        if need > unseen:
            return 0.0
        return sum(
            comb(unseen, k) * (p**k) * ((1 - p) ** (unseen - k)) for k in range(need, unseen + 1)
        )

    def _calculate_delta_bias(self, player: str, face: int, outcomes: list[dict]) -> float:
        relevant = [o for o in outcomes if o["bidder"] == player and o["final_bet"].face == face]
        if not relevant:
            return 0.0
        held = sum(1 for o in relevant if o["bet_held"])
        reliability = held / len(relevant)
        return (0.5 - reliability) * 0.2

    def _calculate_delta_momentum(
        self, bet_history: list[dict], game: int, round_num: int
    ) -> float:
        round_bets = [
            b["bet"] for b in bet_history if b["game"] == game and b["round"] == round_num
        ]
        if len(round_bets) < 2:
            return 0.0
        diffs = [
            round_bets[i].quantity - round_bets[i - 1].quantity for i in range(1, len(round_bets))
        ]
        avg_velocity = sum(diffs) / len(diffs)
        return (1.0 - avg_velocity) * 0.1

    def _calculate_delta_signature(
        self, player: str, face: int, quantity: int, outcomes: list[dict]
    ) -> float:
        relevant = [
            o["final_bet"].quantity
            for o in outcomes
            if o["bidder"] == player and o["final_bet"].face == face and o["bet_held"]
        ]
        if not relevant:
            return 0.0
        mean_qty = sum(relevant) / len(relevant)
        ratio = quantity / mean_qty if mean_qty > 0 else 1.0
        if ratio > 1.5:
            return min(0.1, (ratio - 1.5) * 0.05)
        return 0.0

    def algo(
        self,
        hand: list[int],
        prior_bet: Bet | None,
        total_dice: int,
        bet_history: list[dict],
        outcomes: list[dict],
        stats=None,
    ) -> Bet | None:
        if prior_bet is None:
            best_face = max(range(2, 7), key=lambda f: hand.count(f) + hand.count(1))
            own = hand.count(best_face) + hand.count(1)
            unseen = total_dice - len(hand)
            expected_others = unseen * (2 / 6)
            quantity = max(1, round(own + expected_others * 0.7))
            return Bet(quantity, best_face, self.name)

        p_holds = self._prob_bet_holds(hand, prior_bet.face, prior_bet.quantity, total_dice)

        if stats is not None:
            face_bluff_rate = stats.bluff_rate_by_face.get(prior_bet.player, {}).get(
                prior_bet.face, 0.5
            )
            delta_bias = (0.5 - (1 - face_bluff_rate)) * 0.2

            delta_momentum = (1.0 - stats.current_round_velocity) * 0.1

            mean_qty = stats.mean_held_quantity_by_face.get(prior_bet.player, {}).get(
                prior_bet.face, 0
            )
            if mean_qty > 0:
                ratio = prior_bet.quantity / mean_qty
                delta_sig = min(0.1, (ratio - 1.5) * 0.05) if ratio > 1.5 else 0.0
            else:
                delta_sig = 0.0
        else:
            if not bet_history:
                game, round_num = 0, 0
            else:
                last_entry = bet_history[-1]
                game, round_num = last_entry["game"], last_entry["round"]
            delta_bias = self._calculate_delta_bias(prior_bet.player, prior_bet.face, outcomes)
            delta_momentum = self._calculate_delta_momentum(bet_history, game, round_num)
            delta_sig = self._calculate_delta_signature(
                prior_bet.player, prior_bet.face, prior_bet.quantity, outcomes
            )

        threshold_eff = 0.30 + delta_bias + delta_momentum + delta_sig

        if p_holds < threshold_eff:
            return None

        own_on_face = hand.count(prior_bet.face) + (hand.count(1) if prior_bet.face != 1 else 0)
        if own_on_face > 0:
            return Bet(prior_bet.quantity + 1, prior_bet.face, self.name)

        for face in range(prior_bet.face + 1, 7):
            if hand.count(face) + hand.count(1) > 0:
                return Bet(prior_bet.quantity, face, self.name)

        return Bet(prior_bet.quantity + 1, prior_bet.face, self.name)
```

- [ ] **Step 2: Run full suite**

```bash
uv run pytest tests/ -v
```

Expected: 71 tests pass.

- [ ] **Step 3: Commit**

```bash
git add players/sloane.py
git commit -m "feat(players): migrate Sloane to use GameStats (3 O(n) scans eliminated)"
```

---

## Task 6: Migrate Remy

**Files:**

- Modify: `players/remy.py`

- [ ] **Step 1: Replace `players/remy.py`**

```python
from math import comb

from game.components.bets import Bet


class Remy:
    """
    Revealed-hand opponent modeling strategy.

    Remy exploits two signals that Diego, Finn, Eva, and Zara all ignore:

    1. Revealed hands from `outcomes["hands"]`: every past round's full dice
       are ground truth.  Remy computes a per-player, per-face "density bias"
       — how many more (or fewer) dice of each face that player actually showed
       compared to the uniform expectation.  When an opponent bids on a face
       they historically over-represent, the bid is more credible; when they
       bid on a face they rarely showed, it looks like a bluff.  The bias
       adjusts the effective probability used for the liar/raise decision.

    2. Intra-round bid trajectory from `bet_history`: if the quantity has been
       escalating fast (average jump ≥ 1.5/step), someone has backing and bids
       are more credible.  Slow minimum-raise sequences signal forced bluffing
       and widen the liar window.

    The baseline liar threshold also scales with dice remaining (like Finn) and
    with the bidder's overall bluff rate (Laplace-smoothed, like Zara).
    """

    name = "Remy"

    def _prob_bet_holds(self, hand: list[int], face: int, quantity: int, total_dice: int) -> float:
        own = hand.count(face) + (hand.count(1) if face != 1 else 0)
        unseen = total_dice - len(hand)
        p = 1 / 6 if face == 1 else 2 / 6
        need = quantity - own
        if need <= 0:
            return 1.0
        if need > unseen:
            return 0.0
        return sum(
            comb(unseen, k) * (p**k) * ((1 - p) ** (unseen - k)) for k in range(need, unseen + 1)
        )

    def _face_bias(self, player: str, face: int, outcomes: list[dict]) -> float:
        total_dice_seen = 0
        total_face_seen = 0
        for o in outcomes:
            hands = o.get("hands", {})
            if player not in hands:
                continue
            phand = hands[player]
            total_dice_seen += len(phand)
            total_face_seen += phand.count(face)
            if face != 1:
                total_face_seen += phand.count(1)
        if total_dice_seen == 0:
            return 0.0
        observed_rate = total_face_seen / total_dice_seen
        expected_rate = 2 / 6 if face != 1 else 1 / 6
        return observed_rate - expected_rate

    def _bias_adjustment(self, player: str, face: int, outcomes: list[dict]) -> float:
        rounds_with_player = sum(1 for o in outcomes if player in o.get("hands", {}))
        if rounds_with_player < 2:
            return 0.0
        bias = self._face_bias(player, face, outcomes)
        return -max(-0.08, min(0.08, bias * 0.4))

    def _bias_adjustment_from_stats(self, player: str, face: int, stats) -> float:
        if stats.rounds_with_hand.get(player, 0) < 2:
            return 0.0
        freq = stats.revealed_hand_frequency.get(player, {})
        # For non-1 faces, 1s are wild — add the 1-fraction to match _face_bias behavior.
        if face != 1:
            observed_rate = freq.get(face, 0.0) + freq.get(1, 0.0)
        else:
            observed_rate = freq.get(face, 0.0)
        expected_rate = 2 / 6 if face != 1 else 1 / 6
        bias = observed_rate - expected_rate
        return -max(-0.08, min(0.08, bias * 0.4))

    def _round_velocity(self, bet_history: list[dict], game: int, round_num: int) -> float:
        round_bets = [
            b["bet"] for b in bet_history if b["game"] == game and b["round"] == round_num
        ]
        if len(round_bets) < 2:
            return 1.0
        jumps = [
            round_bets[i].quantity - round_bets[i - 1].quantity for i in range(1, len(round_bets))
        ]
        return sum(jumps) / len(jumps)

    def _velocity_adjustment(self, velocity: float) -> float:
        delta = -(velocity - 1.0) * 0.06
        return max(-0.10, min(0.10, delta))

    def _bluff_rate(self, player: str, outcomes: list[dict]) -> float:
        bluffs = sum(1 for o in outcomes if o["bidder"] == player and not o["bet_held"])
        holds = sum(1 for o in outcomes if o["bidder"] == player and o["bet_held"])
        return (bluffs + 1) / (bluffs + holds + 2)

    def _threshold(
        self,
        bidder: str,
        face: int,
        total_dice: int,
        bet_history: list[dict],
        outcomes: list[dict],
        game: int,
        round_num: int,
        stats=None,
    ) -> float:
        base = 0.30

        if stats is not None:
            bluff_rate = stats.bluff_rate.get(bidder, 0.5)
            bias_adj = self._bias_adjustment_from_stats(bidder, face, stats)
            vel_adj = self._velocity_adjustment(stats.current_round_velocity)
        else:
            bluff_rate = self._bluff_rate(bidder, outcomes)
            bias_adj = self._bias_adjustment(bidder, face, outcomes)
            velocity = self._round_velocity(bet_history, game, round_num)
            vel_adj = self._velocity_adjustment(velocity)

        bluff_offset = (bluff_rate - 0.5) * 0.30
        endgame_adj = -0.05 if total_dice <= 10 else 0.0
        return max(0.10, base + bluff_offset + bias_adj + vel_adj + endgame_adj)

    def _best_raise(self, hand: list[int], prior_bet: Bet, total_dice: int) -> Bet:
        face = prior_bet.face
        own = hand.count(face) + (hand.count(1) if face != 1 else 0)
        if own >= 2:
            return Bet(prior_bet.quantity + 2, face, self.name)
        if own >= 1:
            return Bet(prior_bet.quantity + 1, face, self.name)
        for f in range(face + 1, 7):
            if hand.count(f) + hand.count(1) > 0:
                return Bet(prior_bet.quantity, f, self.name)
        return Bet(prior_bet.quantity + 1, face, self.name)

    def algo(
        self,
        hand: list[int],
        prior_bet: Bet | None,
        total_dice: int,
        bet_history: list[dict],
        outcomes: list[dict],
        stats=None,
    ) -> Bet | None:
        if prior_bet is None:
            best_face = max(range(2, 7), key=lambda f: hand.count(f) + hand.count(1))
            own = hand.count(best_face) + hand.count(1)
            unseen = total_dice - len(hand)
            opening_mult = min(0.82, 0.70 + total_dice * 0.004)
            quantity = max(1, round(own + unseen * (2 / 6) * opening_mult))
            return Bet(quantity, best_face, self.name)

        if bet_history:
            game = bet_history[-1]["game"]
            round_num = bet_history[-1]["round"]
        else:
            game = 1
            round_num = 1

        threshold = self._threshold(
            prior_bet.player,
            prior_bet.face,
            total_dice,
            bet_history,
            outcomes,
            game,
            round_num,
            stats=stats,
        )

        p_holds = self._prob_bet_holds(hand, prior_bet.face, prior_bet.quantity, total_dice)

        if p_holds < threshold:
            return None

        return self._best_raise(hand, prior_bet, total_dice)
```

- [ ] **Step 2: Run full suite**

```bash
uv run pytest tests/ -v
```

Expected: 71 tests pass.

- [ ] **Step 3: Commit**

```bash
git add players/remy.py
git commit -m "feat(players): migrate Remy to use GameStats (4 O(n) scans eliminated)"
```

---

## Task 7: README documentation

**Files:**

- Modify: `README.md`

- [ ] **Step 1: Update the `algo` inputs table**

Find the `algo inputs` table in `README.md` (around line 116). The table currently ends at the `outcomes` row. Add a `stats` row:

```markdown
| `stats` | `GameStats \| None` | Pre-computed opponent statistics. Present only if your `algo` declares a 6th parameter. Use it instead of scanning `bet_history` or `outcomes` — those lists grow to tens of thousands of entries by game 1000 and scanning them on every turn makes your player slow. See `game/components/stats.py` for the full attribute list. |
```

- [ ] **Step 2: Add a performance callout after the table**

After the inputs table and before the `### Return value` heading, add:

```markdown
> **Performance note:** If your strategy reads `bet_history` or `outcomes`, declare `stats=None`
> as a 6th parameter and use `GameStats` instead. A full scan of `outcomes` at game 1000
> iterates ~15,000 entries — done on every turn, that makes the last games ~2,000× slower
> than the first.
```

- [ ] **Step 3: Run full suite one final time**

```bash
uv run pytest tests/ -v
```

Expected: 71 tests pass.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs(game): document GameStats in player API section of README"
```

---

## Done

All 7 tasks complete. Push when ready:

```bash
git push origin main
```
