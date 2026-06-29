# Live Tuning Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a real-time terminal dashboard to simulation runs so bot designers can see live per-game stats (win rate, die-loss cause, head-to-head breakdown, call accuracy) instead of scanning log files after the fact.

**Architecture:** New counters are added to `GameStats`; `run_series` returns a `SeriesResult` dataclass and accepts an `on_game_complete` callback; `game/dashboard.py` renders a two-panel Rich display; new in-process simulation entry points (`game/simulation/season.py`, `game/simulation/tournament.py`) replace the subprocess chain so the dashboard can aggregate across series within a run.

**Tech Stack:** Python 3.11+, `rich` (new dependency), existing `game.components.series`, `game.components.stats`, `game.components.script`.

## Global Constraints

- Always use `uv run python` — never bare `python3` or `python`.
- Run engine tests with `just pytest-all`; player tests with `just pytest-players`.
- Commit type/scope must pass commitlint (`.commitlintrc.mjs`). Valid scopes include `engine`, `dashboard`, `sim`, `specs`, `plans`. Types that bump version: `feat` (minor), `fix`/`perf` (patch). Others do not bump.
- All PRs: footer must include `🤖 Co-Authored with [Claude Code](https://claude.com/claude-code)`.
- Never commit to `main` — always use a branch.
- All test files live in `tests/` (engine tests) or `player_tests/` (gitignored, local only).

---

### Task 1: GameStats new counters and `record_penalty` method

**Files:**

- Modify: `game/components/stats.py`
- Test: `tests/test_main.py` (add new tests at bottom of file)

**Interfaces:**

- Produces (properties): `die_losses_from_bluff`, `die_losses_from_challenge`, `challenge_success_by_face`, `challenge_count_by_face`, `rounds_played`, `games_played`, `penalty_count`
- Produces (method): `record_penalty(player_name: str) -> None`
- `update_outcome(outcome)` — existing method, gains new counter updates
- `start_game(player_names)` — existing method, now also increments `games_played`

- [ ] **Step 1.1: Write failing tests**

Add to the bottom of `tests/test_main.py`:

```python
def _make_outcome(bidder, challenger, bet_held, loser, hands, face=2):
    """Helper: build a minimal outcome dict for stats testing."""
    from game.components.bets import Bet
    return {
        "game": 1, "round": 1,
        "hands": {k: tuple(v) for k, v in hands.items()},
        "final_bet": Bet(1, face, bidder),
        "bidder": bidder, "challenger": challenger,
        "bet_held": bet_held, "loser": loser,
    }


def test_die_losses_from_bluff_tracked():
    """die_losses_from_bluff[loser][challenger] increments when bid fails."""
    from game.components.stats import GameStats
    s = GameStats()
    s.start_game(["Alice", "Bruno"])
    outcome = _make_outcome(
        bidder="Alice", challenger="Bruno",
        bet_held=False, loser="Alice",
        hands={"Alice": (1,), "Bruno": (2,)},
    )
    s.update_outcome(outcome)
    assert s.die_losses_from_bluff.get("Alice", {}).get("Bruno", 0) == 1
    assert s.die_losses_from_challenge.get("Bruno", {}).get("Alice", 0) == 0


def test_die_losses_from_challenge_tracked():
    """die_losses_from_challenge[loser][bidder] increments when call fails."""
    from game.components.stats import GameStats
    s = GameStats()
    s.start_game(["Alice", "Bruno"])
    outcome = _make_outcome(
        bidder="Alice", challenger="Bruno",
        bet_held=True, loser="Bruno",
        hands={"Alice": (2,), "Bruno": (1,)},
    )
    s.update_outcome(outcome)
    assert s.die_losses_from_challenge.get("Bruno", {}).get("Alice", 0) == 1
    assert s.die_losses_from_bluff.get("Alice", {}).get("Bruno", 0) == 0


def test_challenge_accuracy_by_face_tracked():
    """challenge_success_by_face and challenge_count_by_face increment on calls."""
    from game.components.stats import GameStats
    s = GameStats()
    s.start_game(["Alice", "Bruno"])
    success = _make_outcome("Alice", "Bruno", bet_held=False, loser="Alice",
                             hands={"Alice": (1,), "Bruno": (2,)}, face=3)
    fail = _make_outcome("Alice", "Bruno", bet_held=True, loser="Bruno",
                          hands={"Alice": (3,), "Bruno": (2,)}, face=3)
    s.update_outcome(success)
    s.update_outcome(fail)
    assert s.challenge_count_by_face.get("Bruno", {}).get(3, 0) == 2
    assert s.challenge_success_by_face.get("Bruno", {}).get(3, 0) == 1


def test_rounds_played_increments_per_hand_participant():
    """rounds_played increments for every player present in hands each round."""
    from game.components.stats import GameStats
    s = GameStats()
    s.start_game(["Alice", "Bruno", "Cleo"])
    outcome = _make_outcome("Alice", "Bruno", bet_held=False, loser="Alice",
                             hands={"Alice": (1,), "Bruno": (2,), "Cleo": (3,)})
    s.update_outcome(outcome)
    assert s.rounds_played.get("Alice", 0) == 1
    assert s.rounds_played.get("Bruno", 0) == 1
    assert s.rounds_played.get("Cleo", 0) == 1


def test_games_played_increments_on_start_game():
    """games_played increments for each player when start_game is called."""
    from game.components.stats import GameStats
    s = GameStats()
    s.start_game(["Alice", "Bruno"])
    s.start_game(["Alice", "Bruno"])
    assert s.games_played.get("Alice", 0) == 2
    assert s.games_played.get("Bruno", 0) == 2


def test_record_penalty_increments():
    """record_penalty increments penalty_count for the named player."""
    from game.components.stats import GameStats
    s = GameStats()
    s.start_game(["Alice", "Bruno"])
    s.record_penalty("Alice")
    s.record_penalty("Alice")
    s.record_penalty("Bruno")
    assert s.penalty_count.get("Alice", 0) == 2
    assert s.penalty_count.get("Bruno", 0) == 1
```

- [ ] **Step 1.2: Run tests to confirm they fail**

```bash
just pytest tests/test_main.py::test_die_losses_from_bluff_tracked \
             tests/test_main.py::test_die_losses_from_challenge_tracked \
             tests/test_main.py::test_challenge_accuracy_by_face_tracked \
             tests/test_main.py::test_rounds_played_increments_per_hand_participant \
             tests/test_main.py::test_games_played_increments_on_start_game \
             tests/test_main.py::test_record_penalty_increments
```

Expected: FAIL with `AttributeError: 'GameStats' object has no attribute ...`

- [ ] **Step 1.3: Add new backing stores to `GameStats.__init__`**

In `game/components/stats.py`, inside `__init__`, after the `_current_round_bets` line, add:

```python
        # Backing stores: die-loss tracking per opponent
        self._die_losses_from_bluff: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self._die_losses_from_challenge: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

        # Backing stores: per-face call accuracy
        self._challenge_success_by_face: dict[str, dict[int, int]] = defaultdict(lambda: defaultdict(int))
        self._challenge_count_by_face: dict[str, dict[int, int]] = defaultdict(lambda: defaultdict(int))

        # Backing stores: rounds/games counters
        self._rounds_played: dict[str, int] = defaultdict(int)
        self._games_played: dict[str, int] = defaultdict(int)

        # Backing store: penalty count
        self._penalty_count: dict[str, int] = defaultdict(int)
```

- [ ] **Step 1.4: Add read-only properties**

After the existing `dice_counts` property, add:

```python
    @property
    def die_losses_from_bluff(self) -> dict[str, dict[str, int]]:
        return {k: dict(v) for k, v in self._die_losses_from_bluff.items()}

    @property
    def die_losses_from_challenge(self) -> dict[str, dict[str, int]]:
        return {k: dict(v) for k, v in self._die_losses_from_challenge.items()}

    @property
    def challenge_success_by_face(self) -> dict[str, dict[int, int]]:
        return {k: dict(v) for k, v in self._challenge_success_by_face.items()}

    @property
    def challenge_count_by_face(self) -> dict[str, dict[int, int]]:
        return {k: dict(v) for k, v in self._challenge_count_by_face.items()}

    @property
    def rounds_played(self) -> dict[str, int]:
        return dict(self._rounds_played)

    @property
    def games_played(self) -> dict[str, int]:
        return dict(self._games_played)

    @property
    def penalty_count(self) -> dict[str, int]:
        return dict(self._penalty_count)
```

- [ ] **Step 1.5: Update `start_game` to increment `games_played`**

Replace the existing `start_game` method body:

```python
    def start_game(self, player_names: list[str]) -> None:
        """Call at the start of each game. Resets dice_counts to 5 for all players."""
        self._dice_counts = {name: 5 for name in player_names}
        for name in player_names:
            self._games_played[name] += 1
```

- [ ] **Step 1.6: Update `update_outcome` to populate new counters**

At the end of `update_outcome`, before the closing of the method (after the `dice_counts` block), add:

```python
        # Die-loss tracking per opponent
        if not bet_held:
            # bidder's bluff was caught — bidder lost a die, challenger won it
            self._die_losses_from_bluff[bidder][challenger] += 1
        else:
            # challenger's call was wrong — challenger lost a die, bidder won it
            self._die_losses_from_challenge[challenger][bidder] += 1

        # Per-face call accuracy
        face = final_bet.face
        self._challenge_count_by_face[challenger][face] += 1
        if not bet_held:
            self._challenge_success_by_face[challenger][face] += 1

        # Rounds survived: every player present in hands this round
        for player_name in hands:
            self._rounds_played[player_name] += 1
```

Note: `final_bet` and `face` are already extracted earlier in `update_outcome`. Use the existing `face` local variable on the `raw_bluff_rate_by_face` line — it is set as `face = final_bet.face`. Add the new code after the `dice_counts` block, not before.

- [ ] **Step 1.7: Add `record_penalty` method**

After `reset_round`, add:

```python
    def record_penalty(self, player_name: str) -> None:
        """Call when a player incurs a penalty (exception, invalid bid, liar-with-no-bet)."""
        self._penalty_count[player_name] += 1
```

- [ ] **Step 1.8: Run tests to confirm they pass**

```bash
just pytest tests/test_main.py::test_die_losses_from_bluff_tracked \
             tests/test_main.py::test_die_losses_from_challenge_tracked \
             tests/test_main.py::test_challenge_accuracy_by_face_tracked \
             tests/test_main.py::test_rounds_played_increments_per_hand_participant \
             tests/test_main.py::test_games_played_increments_on_start_game \
             tests/test_main.py::test_record_penalty_increments
```

Expected: PASS (6 passed)

- [ ] **Step 1.9: Run full test suite**

```bash
just pytest-all
```

Expected: all existing tests pass.

- [ ] **Step 1.10: Commit**

```bash
git add game/components/stats.py tests/test_main.py
git commit -m "$(cat <<'EOF'
feat(engine): add die-loss, call-accuracy, rounds, penalty counters to GameStats

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: `SeriesResult` dataclass and updated `run_series` signature

**Files:**

- Modify: `game/components/series.py`
- Modify: `game/__main__.py`
- Modify: `tests/test_main.py`

**Interfaces:**

- Produces: `SeriesResult` dataclass with fields `wins: dict[str, int]`, `stats: GameStats`, `outcomes: list[dict] | None`
- `run_series(players, n_games, tier=None, capture_outcomes=False, on_game_complete=None) -> SeriesResult`
- `on_game_complete` signature: `(game_num: int, wins: dict[str, int], stats: GameStats) -> None`

- [ ] **Step 2.1: Write failing tests**

Add to `tests/test_main.py`:

```python
def test_run_series_returns_series_result():
    """run_series returns a SeriesResult with wins and stats fields."""
    from game.components.series import SeriesResult, run_series

    class AlwaysBid:
        name = "A"
        def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):
            from game.components.bets import Bet
            return Bet(1, 2, self.name) if prior_bet is None else Bet(prior_bet.quantity + 1, prior_bet.face, self.name)

    class AlwaysCall:
        name = "B"
        def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):
            return None

    result = run_series([AlwaysBid(), AlwaysCall()], n_games=3)
    assert isinstance(result, SeriesResult)
    assert isinstance(result.wins, dict)
    assert sum(result.wins.values()) == 3
    assert result.stats is not None
    assert result.outcomes is None  # capture_outcomes defaults to False


def test_run_series_capture_outcomes():
    """run_series with capture_outcomes=True populates SeriesResult.outcomes."""
    from game.components.series import run_series

    class AlwaysBid:
        name = "A"
        def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):
            from game.components.bets import Bet
            return Bet(1, 2, self.name) if prior_bet is None else Bet(prior_bet.quantity + 1, prior_bet.face, self.name)

    class AlwaysCall:
        name = "B"
        def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):
            return None

    result = run_series([AlwaysBid(), AlwaysCall()], n_games=2, capture_outcomes=True)
    assert result.outcomes is not None
    assert len(result.outcomes) > 0


def test_on_game_complete_fires_each_game():
    """on_game_complete is called once per game with current wins and stats."""
    from game.components.series import run_series
    from game.components.stats import GameStats

    calls = []

    def callback(game_num, wins, stats):
        calls.append((game_num, dict(wins), isinstance(stats, GameStats)))

    class AlwaysBid:
        name = "A"
        def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):
            from game.components.bets import Bet
            return Bet(1, 2, self.name) if prior_bet is None else Bet(prior_bet.quantity + 1, prior_bet.face, self.name)

    class AlwaysCall:
        name = "B"
        def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):
            return None

    run_series([AlwaysBid(), AlwaysCall()], n_games=5, on_game_complete=callback)
    assert len(calls) == 5
    assert calls[0][0] == 1
    assert calls[4][0] == 5
    assert all(c[2] for c in calls)  # each call received a GameStats
```

- [ ] **Step 2.2: Run tests to confirm they fail**

```bash
just pytest tests/test_main.py::test_run_series_returns_series_result \
             tests/test_main.py::test_run_series_capture_outcomes \
             tests/test_main.py::test_on_game_complete_fires_each_game
```

Expected: FAIL — `ImportError: cannot import name 'SeriesResult'` or similar.

- [ ] **Step 2.3: Rewrite `game/components/series.py`**

Replace the entire file:

```python
import logging
from collections.abc import Callable
from dataclasses import dataclass

from game.components.stats import GameStats

logger = logging.getLogger(__name__)


@dataclass
class SeriesResult:
    wins: dict[str, int]
    stats: GameStats
    outcomes: list[dict] | None = None


def run_series(
    players: list,
    n_games: int,
    tier: str | None = None,
    capture_outcomes: bool = False,
    on_game_complete: Callable[[int, dict[str, int], GameStats], None] | None = None,
) -> SeriesResult:
    """Runs n_games games between the given players and returns a SeriesResult.

    Args:
        players: List of player objects, each implementing the algo interface.
        n_games: Number of games to play.
        tier: League tier for this series ("L1", "CH", "PRM"), or None for
              tournament pools and untiered runs.
        capture_outcomes: If True, all round outcomes are included in the
              returned SeriesResult.outcomes. Defaults to False (outcomes not
              returned to caller, saving ~14 MB per 1000-game series).
        on_game_complete: Optional callback fired after each game with
              (game_num, wins, stats). Runs synchronously — no threading,
              no torn reads.

    Returns:
        SeriesResult with wins, stats, and optionally outcomes.
    """
    from game.components.script import game_orchestrator

    wins = {p.name: 0 for p in players}
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
            players,
            game_id=game_num,
            bet_history=bet_history,
            outcomes=outcomes,
            stats=stats,
            tier=tier,
        )
        wins[winner.name] += 1
        logger.info(f"Game {game_num}/{n_games}: {winner.name} wins")

        if on_game_complete is not None:
            on_game_complete(game_num, wins, stats)

    return SeriesResult(
        wins=wins,
        stats=stats,
        outcomes=outcomes if capture_outcomes else None,
    )


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

- [ ] **Step 2.4: Update `game/__main__.py` to unpack `SeriesResult`**

In `game/__main__.py`, find line 120:

```python
wins = run_series(players, N_GAMES, tier=args.tier)
```

Replace with:

```python
result = run_series(players, N_GAMES, tier=args.tier)
wins = result.wins
```

- [ ] **Step 2.5: Run new tests**

```bash
just pytest tests/test_main.py::test_run_series_returns_series_result \
             tests/test_main.py::test_run_series_capture_outcomes \
             tests/test_main.py::test_on_game_complete_fires_each_game
```

Expected: PASS (3 passed)

- [ ] **Step 2.6: Run full test suite**

```bash
just pytest-all
```

Expected: all pass (some tests call `run_series` and don't check the return type — they will still pass since they don't unpack the result).

- [ ] **Step 2.7: Commit**

```bash
git add game/components/series.py game/__main__.py tests/test_main.py
git commit -m "$(cat <<'EOF'
feat(engine): SeriesResult dataclass and on_game_complete callback in run_series

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: `record_penalty` calls in `game_orchestrator`

**Files:**

- Modify: `game/components/script.py`
- Test: `tests/test_main.py`

**Interfaces:**

- Consumes: `GameStats.record_penalty(player_name: str)` from Task 1

- [ ] **Step 3.1: Write failing test**

Add to `tests/test_main.py`:

```python
def test_penalty_count_on_exception(tmp_path):
    """A player that raises an exception is penalised — penalty_count increments."""
    import textwrap
    from game.components.series import run_series
    from game.components.utils import import_player_classes_from_dir

    player_src = textwrap.dedent("""
        from game.components.bets import Bet

        class Crasher:
            name = "Crasher"
            def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):
                raise RuntimeError("boom")
    """)
    player_dir = tmp_path / "players"
    player_dir.mkdir()
    (player_dir / "crasher.py").write_text(player_src)
    (player_dir / "__init__.py").write_text("")

    class AlwaysBid:
        name = "AlwaysBid"
        def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):
            from game.components.bets import Bet
            return Bet(1, 2, self.name) if prior_bet is None else Bet(prior_bet.quantity + 1, prior_bet.face, self.name)

    players = import_player_classes_from_dir(str(player_dir))
    result = run_series(players + [AlwaysBid()], n_games=3)
    assert result.stats.penalty_count.get("Crasher", 0) == 3
```

- [ ] **Step 3.2: Run test to confirm it fails**

```bash
just pytest tests/test_main.py::test_penalty_count_on_exception
```

Expected: FAIL — `assert 0 == 3`

- [ ] **Step 3.3: Add `record_penalty` calls to the three penalty paths in `game_orchestrator`**

In `game/components/script.py`, find the three `loser = player_idx` assignments that happen WITHOUT calling `update_outcome`. Add `stats.record_penalty(player.name)` after each one.

**Penalty path 1** — exception handler (around line 157):

```python
            except Exception:
                logger.error(
                    "%s raised an exception - penalised\n%s",
                    player.name,
                    traceback.format_exc().rstrip(),
                )
                loser = player_idx
                if stats is not None:
                    stats.record_penalty(player.name)
                break
```

**Penalty path 2** — liar with no prior bet (around line 163):

```python
                if current_bet is None:
                    logger.warning(f"{player.name} called liar with no prior bet - penalised")
                    loser = player_idx
                    if stats is not None:
                        stats.record_penalty(player.name)
```

**Penalty path 3** — invalid bid validation (around line 202):

```python
            else:
                # Player makes a new bid
                if ones_allowed is False and action.face == 1:
                    logger.warning(f"{player.name} bid on 1s after non-1 opening bid - penalised")
                    loser = player_idx
                    if stats is not None:
                        stats.record_penalty(player.name)
                elif current_bet is not None and not bet_validator(current_bet, action):
                    logger.warning(f"{player.name} made invalid bid [{action}] - penalised")
                    loser = player_idx
                    if stats is not None:
                        stats.record_penalty(player.name)
```

- [ ] **Step 3.4: Run test to confirm it passes**

```bash
just pytest tests/test_main.py::test_penalty_count_on_exception
```

Expected: PASS

- [ ] **Step 3.5: Run full test suite**

```bash
just pytest-all
```

Expected: all pass.

- [ ] **Step 3.6: Commit**

```bash
git add game/components/script.py tests/test_main.py
git commit -m "$(cat <<'EOF'
fix(engine): record_penalty on all three penalty paths in game_orchestrator

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Dashboard module (`game/dashboard.py`) and `rich` dependency

**Files:**

- Create: `game/dashboard.py`
- Modify: `pyproject.toml`
- Test: `tests/test_main.py`

**Interfaces:**

- Consumes: `GameStats` (Task 1 properties), `SeriesResult` (Task 2)
- Produces: `Dashboard(watched, n_games)` context manager with `.update(game_num, wins, stats)` and `.on_series_complete(label, result)`
- Produces: `PlayerAggregate` dataclass (internal accumulator, but importable)

`PANEL_HEIGHT = 18` — fixed constant used for terminal clipping.

- [ ] **Step 4.1: Add `rich` to `pyproject.toml`**

In `pyproject.toml`, change:

```toml
dependencies = ["pandas", "pyyaml"]
```

to:

```toml
dependencies = ["pandas", "pyyaml", "rich"]
```

Then run:

```bash
uv sync
```

- [ ] **Step 4.2: Write a failing smoke test**

Add to `tests/test_main.py`:

```python
def test_dashboard_context_manager_no_crash():
    """Dashboard can be entered and exited without error (no terminal, no crash)."""
    from game.dashboard import Dashboard
    from game.components.stats import GameStats

    wins = {"Oracle": 0, "EvilStewie": 0}
    stats = GameStats()
    stats.start_game(["Oracle", "EvilStewie"])

    # Use force_jupyter=False and Console(quiet=True) path via watched=[]
    dash = Dashboard(watched=["Oracle"], n_games=10)
    with dash:
        wins["Oracle"] += 1
        dash.update(1, wins, stats)
```

- [ ] **Step 4.3: Run test to confirm it fails**

```bash
just pytest tests/test_main.py::test_dashboard_context_manager_no_crash
```

Expected: FAIL — `ModuleNotFoundError: No module named 'game.dashboard'`

- [ ] **Step 4.4: Create `game/dashboard.py`**

```python
"""Live terminal dashboard for bot tuning. Renders per-game stats via rich.Live."""
from __future__ import annotations

from collections import defaultdict
from contextlib import nullcontext
from dataclasses import dataclass, field

from rich.columns import Columns
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

PANEL_HEIGHT = 18
_BAR_W = 20
_BAR_FULL = "█"
_BAR_EMPTY = "░"


@dataclass
class PlayerAggregate:
    """Cumulative stats for the right panel, accumulated across series."""
    total_games: int = 0
    wins: int = 0
    die_losses_from_bluff: dict[str, int] = field(default_factory=dict)
    die_losses_from_challenge: dict[str, int] = field(default_factory=dict)
    die_wins_from_bluff: dict[str, int] = field(default_factory=dict)
    die_wins_from_challenge: dict[str, int] = field(default_factory=dict)
    rounds_played: int = 0
    penalties: int = 0
    challenge_successes: int = 0
    challenge_total: int = 0
    challenge_success_by_face: dict[int, int] = field(default_factory=dict)
    challenge_total_by_face: dict[int, int] = field(default_factory=dict)


def _bar(value: float, total: float, width: int = _BAR_W) -> str:
    if total <= 0:
        return _BAR_EMPTY * width
    filled = round(value / total * width)
    return _BAR_FULL * filled + _BAR_EMPTY * (width - filled)


def _pct(num: int, den: int) -> str:
    return f"{num / den * 100:.1f}%" if den else "—"


def _render_left(
    player: str,
    game_num: int,
    n_games: int,
    wins: dict[str, int],
    stats,
) -> str:
    """Build text for the left 'This Week' panel."""
    w = wins.get(player, 0)
    gp = stats.games_played.get(player, 0) or 1
    win_pct = w / gp
    rp = stats.rounds_played.get(player, 0)
    avg_rounds = rp / gp if gp else 0.0
    pen = stats.penalty_count.get(player, 0)

    bluff_losses = stats.die_losses_from_bluff.get(player, {})
    call_losses = stats.die_losses_from_challenge.get(player, {})
    bad_bluff = sum(bluff_losses.values())
    bad_call = sum(call_losses.values())
    total_losses = bad_bluff + bad_call

    lines = [
        f"Win Rate  {_pct(w, gp):>7}  {_bar(w, gp)}",
        f"Avg Rounds {avg_rounds:>5.1f}/game   Penalties {pen:>3}",
        "",
        f"Die Losses  {total_losses} total",
        f"  Bad bluff  {bad_bluff:>5}  {_pct(bad_bluff, total_losses):>6}  {_bar(bad_bluff, total_losses)}",
        f"  Bad call   {bad_call:>5}  {_pct(bad_call, total_losses):>6}  {_bar(bad_call, total_losses)}",
        "",
        "Head-to-Head  Lost        Won       Net",
        "              Bluff/Call  Bluff/Call",
    ]

    bluff_wins = stats.die_losses_from_bluff
    call_wins = stats.die_losses_from_challenge
    opponents = sorted(
        set(bluff_losses) | set(call_losses)
        | {opp for opp, v in bluff_wins.items() if player in v}
        | {opp for opp, v in call_wins.items() if player in v}
    )
    for opp in opponents[:5]:
        lb = bluff_losses.get(opp, 0)
        lc = call_losses.get(opp, 0)
        wb = bluff_wins.get(opp, {}).get(player, 0)
        wc = call_wins.get(opp, {}).get(player, 0)
        net = (wb + wc) - (lb + lc)
        sign = "+" if net >= 0 else ""
        lines.append(
            f"  {opp:<12}  {lb:>3}/{lc:<3}    {wb:>3}/{wc:<3}  {sign}{net}"
        )

    cs_by_face = stats.challenge_success_by_face.get(player, {})
    cc_by_face = stats.challenge_count_by_face.get(player, {})
    total_cs = sum(cs_by_face.values())
    total_cc = sum(cc_by_face.values())
    face_str = "  ".join(
        f"{f}:{_pct(cs_by_face.get(f, 0), cc_by_face.get(f, 0))}"
        for f in range(1, 7)
    )
    lines += [
        "",
        f"Call Accuracy  {_pct(total_cs, total_cc)} overall",
        face_str,
    ]

    return "\n".join(lines)


def _render_right(player: str, agg: PlayerAggregate) -> str:
    """Build text for the right 'Sim Total' panel."""
    gp = agg.total_games or 1
    win_pct = agg.wins / gp
    avg_rounds = agg.rounds_played / gp if gp else 0.0
    pen = agg.penalties

    bad_bluff = sum(agg.die_losses_from_bluff.values())
    bad_call = sum(agg.die_losses_from_challenge.values())
    total_losses = bad_bluff + bad_call

    lines = [
        f"Win Rate  {_pct(agg.wins, gp):>7}  {_bar(agg.wins, gp)}",
        f"Avg Rounds {avg_rounds:>5.1f}/game   Penalties {pen:>3}",
        "",
        f"Die Losses  {total_losses} total",
        f"  Bad bluff  {bad_bluff:>5}  {_pct(bad_bluff, total_losses):>6}  {_bar(bad_bluff, total_losses)}",
        f"  Bad call   {bad_call:>5}  {_pct(bad_call, total_losses):>6}  {_bar(bad_call, total_losses)}",
        "",
        "Head-to-Head  Lost        Won       Net",
        "              Bluff/Call  Bluff/Call",
    ]

    opponents = sorted(
        set(agg.die_losses_from_bluff) | set(agg.die_losses_from_challenge)
        | set(agg.die_wins_from_bluff) | set(agg.die_wins_from_challenge)
    )
    for opp in opponents[:5]:
        lb = agg.die_losses_from_bluff.get(opp, 0)
        lc = agg.die_losses_from_challenge.get(opp, 0)
        wb = agg.die_wins_from_bluff.get(opp, 0)
        wc = agg.die_wins_from_challenge.get(opp, 0)
        net = (wb + wc) - (lb + lc)
        sign = "+" if net >= 0 else ""
        lines.append(
            f"  {opp:<12}  {lb:>3}/{lc:<3}    {wb:>3}/{wc:<3}  {sign}{net}"
        )

    total_cs = sum(agg.challenge_success_by_face.values())
    total_cc = sum(agg.challenge_total_by_face.values())
    face_str = "  ".join(
        f"{f}:{_pct(agg.challenge_success_by_face.get(f, 0), agg.challenge_total_by_face.get(f, 0))}"
        for f in range(1, 7)
    )
    lines += [
        "",
        f"Call Accuracy  {_pct(total_cs, total_cc)} overall",
        face_str,
    ]

    return "\n".join(lines)


class Dashboard:
    """Two-panel live terminal dashboard for watched players during a simulation.

    Usage:
        with Dashboard(watched=["Oracle", "EvilStewie"], n_games=1000) as dash:
            result = run_series(players, 1000, on_game_complete=dash.update)
            dash.on_series_complete("CH Tier", result)
    """

    def __init__(self, watched: list[str], n_games: int) -> None:
        self._watched = watched
        self._n_games = n_games
        self._console = Console(stderr=True)
        max_visible = max(1, self._console.height // PANEL_HEIGHT)
        self._visible = watched[:max_visible]
        self._clipped = watched[max_visible:]
        self._aggregates: dict[str, PlayerAggregate] = {
            p: PlayerAggregate() for p in self._visible
        }
        self._current_wins: dict[str, int] = {}
        self._current_stats = None
        self._current_game = 0
        self._live: Live | None = None

    def __enter__(self) -> "Dashboard":
        if self._clipped:
            self._console.print(
                f"[yellow]Dashboard: terminal too small to show "
                f"{', '.join(self._clipped)} — increase height or watch fewer players[/yellow]"
            )
        self._live = Live(
            self._build_renderable(),
            console=self._console,
            refresh_per_second=4,
        )
        self._live.__enter__()
        return self

    def __exit__(self, *args) -> None:
        if self._live:
            self._live.__exit__(*args)

    def update(self, game_num: int, wins: dict[str, int], stats) -> None:
        """Called by on_game_complete after each game."""
        self._current_game = game_num
        self._current_wins = wins
        self._current_stats = stats
        if self._live:
            self._live.update(self._build_renderable())

    def on_series_complete(self, label: str, result) -> None:
        """Called once per run_series call to accumulate right-panel totals."""
        for player in self._visible:
            agg = self._aggregates[player]
            stats = result.stats
            w = result.wins.get(player, 0)
            gp = stats.games_played.get(player, 0)
            agg.total_games += gp
            agg.wins += w
            agg.rounds_played += stats.rounds_played.get(player, 0)
            agg.penalties += stats.penalty_count.get(player, 0)

            for opp, count in stats.die_losses_from_bluff.get(player, {}).items():
                agg.die_losses_from_bluff[opp] = agg.die_losses_from_bluff.get(opp, 0) + count
            for opp, count in stats.die_losses_from_challenge.get(player, {}).items():
                agg.die_losses_from_challenge[opp] = agg.die_losses_from_challenge.get(opp, 0) + count

            # wins from opponents = opponents' losses attributed to this player
            bluff_wins = stats.die_losses_from_bluff
            call_wins = stats.die_losses_from_challenge
            for opp in stats.games_played:
                if opp == player:
                    continue
                wb = bluff_wins.get(opp, {}).get(player, 0)
                wc = call_wins.get(opp, {}).get(player, 0)
                if wb:
                    agg.die_wins_from_bluff[opp] = agg.die_wins_from_bluff.get(opp, 0) + wb
                if wc:
                    agg.die_wins_from_challenge[opp] = agg.die_wins_from_challenge.get(opp, 0) + wc

            for face in range(1, 7):
                cs = stats.challenge_success_by_face.get(player, {}).get(face, 0)
                cc = stats.challenge_count_by_face.get(player, {}).get(face, 0)
                agg.challenge_success_by_face[face] = agg.challenge_success_by_face.get(face, 0) + cs
                agg.challenge_total_by_face[face] = agg.challenge_total_by_face.get(face, 0) + cc
            agg.challenge_successes = sum(agg.challenge_success_by_face.values())
            agg.challenge_total = sum(agg.challenge_total_by_face.values())

    def _build_renderable(self):
        panels = []
        for player in self._visible:
            left_title = f"{player}: This Week — Game {self._current_game}/{self._n_games}"
            right_title = f"{player}: Sim Total — {self._aggregates[player].total_games:,} games"

            if self._current_stats is not None:
                left_body = _render_left(
                    player, self._current_game, self._n_games,
                    self._current_wins, self._current_stats,
                )
            else:
                left_body = "Waiting for first game…"

            right_body = _render_right(player, self._aggregates[player])

            panels.append(
                Columns([
                    Panel(left_body, title=left_title),
                    Panel(right_body, title=right_title),
                ])
            )

        from rich.console import Group
        return Group(*panels)
```

- [ ] **Step 4.5: Run smoke test**

```bash
just pytest tests/test_main.py::test_dashboard_context_manager_no_crash
```

Expected: PASS

- [ ] **Step 4.6: Run full test suite**

```bash
just pytest-all
```

Expected: all pass.

- [ ] **Step 4.7: Commit**

```bash
git add game/dashboard.py pyproject.toml uv.lock tests/test_main.py
git commit -m "$(cat <<'EOF'
feat(dashboard): add live tuning dashboard module with rich two-panel layout

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: `game/simulation/season.py` — in-process season simulation

**Files:**

- Create: `game/simulation/season.py`
- Test: `tests/test_main.py`

**Interfaces:**

- Consumes: `run_series` (Task 2), `GameStats` (Task 1), `Dashboard` (Task 4)
- Consumes: `apply_season_results`, `settle_relegations` from `game.components.leaderboard`
- Consumes: `_load_lb` from `game.season.utils`
- Produces: `run_season(n_games, top_n, lb_path, dashboard=None) -> dict[str, dict[str, int]]`
- Produces: `main()` — CLI entry point with `--date`, `--n-games`, `--top-n`, `--dashboard-players`

The `run_season` function runs one Monday's tier games in-process (bottom-up: inactive → L1 → CH → PRM). L1 pools when > 9 players. Returns `{tier: wins_dict}`.

`_POOL_MAX = 9` — same constant as `run_season.py`.

- [ ] **Step 5.1: Write failing smoke test**

Add to `tests/test_main.py`:

```python
def test_simulation_season_run_season(tmp_path):
    """run_season runs tier games in-process and updates the leaderboard."""
    import textwrap
    import yaml
    from game.simulation.season import run_season

    # Build a minimal leaderboard with 2 L1 players
    lb = {
        "players": {
            "AliceBot": {"tier": "L1", "tier_stats": {}, "tier_since": "2026-01-01T00:00:00Z"},
            "BrunoBot": {"tier": "L1", "tier_stats": {}, "tier_since": "2026-01-01T00:00:00Z"},
        }
    }
    lb_path = str(tmp_path / "leaderboard.yaml")
    with open(lb_path, "w") as f:
        yaml.dump(lb, f)

    # Write stub player files
    players_dir = tmp_path / "players"
    players_dir.mkdir()
    for name in ("AliceBot", "BrunoBot"):
        (players_dir / f"{name.lower()}.py").write_text(textwrap.dedent(f"""
            from game.components.bets import Bet
            class {name}:
                name = "{name}"
                def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):
                    if prior_bet is None:
                        return Bet(1, 2, self.name)
                    return None
        """))
    (players_dir / "__init__.py").write_text("")

    results = run_season(
        n_games=5, top_n=4, lb_path=lb_path, players_dir=str(players_dir)
    )
    assert "L1" in results
    assert sum(results["L1"].values()) == 5
```

- [ ] **Step 5.2: Run test to confirm it fails**

```bash
just pytest tests/test_main.py::test_simulation_season_run_season
```

Expected: FAIL — `ModuleNotFoundError: No module named 'game.simulation.season'`

- [ ] **Step 5.3: Create `game/simulation/season.py`**

```python
"""In-process season simulation for local bot tuning.

Replaces the subprocess-based approach of run_season.py for simulation use cases.
Does not post to GitHub or update README — DRY_RUN-safe by design.
"""
from __future__ import annotations

import argparse
import math
import os
from contextlib import nullcontext
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent.parent
_POOL_MAX = 9


def run_season(
    n_games: int,
    top_n: int,
    lb_path: str,
    players_dir: str | None = None,
    dashboard=None,
) -> dict[str, dict[str, int]]:
    """Run one season step in-process. Returns {tier: {player: win_count}}.

    Args:
        n_games: Games per tier/pool.
        top_n: League capacity per PRM/CH tier (TOP_N).
        lb_path: Path to leaderboard.yaml.
        players_dir: Path to players/ directory. Defaults to repo root / players.
        dashboard: Optional Dashboard instance for live display.
    """
    from game.components.leaderboard import (
        apply_season_results,
        get_tier_players,
        settle_relegations,
    )
    from game.components.series import format_results, run_series
    from game.components.utils import apply_display_names, import_player_classes_from_dir
    from game.season.utils import _load_lb, form_pools

    if players_dir is None:
        players_dir = str(_REPO_ROOT / "players")

    tier_order = ["inactive", "L1", "CH", "PRM"]
    tier_results: dict[str, dict[str, int]] = {}

    for tier in tier_order:
        data = _load_lb(lb_path)
        tier_player_names = set(get_tier_players(data, tier))

        all_players = import_player_classes_from_dir(players_dir)
        apply_display_names(all_players, data.get("players", {}))
        players = [p for p in all_players if type(p).__name__ in tier_player_names]

        if len(players) < 2:
            print(f"[skip] {tier}: {len(players)} player(s) — need ≥ 2 to run games.")
            continue

        if tier == "L1" and len(players) > _POOL_MAX:
            n_pools = math.ceil(len(players) / _POOL_MAX)
            players_by_name = {type(p).__name__: p for p in players}
            seeded_names = sorted(
                tier_player_names,
                key=lambda n: -data["players"].get(n, {})
                .get("tier_stats", {})
                .get("L1", {})
                .get("win_pct", 0.0),
            )
            pools_names = form_pools(seeded_names, n_pools)
            wins: dict[str, int] = {}
            for i, pool_names in enumerate(pools_names):
                pool = [players_by_name[n] for n in pool_names if n in players_by_name]
                print(f"[run] L1 pool {i + 1}/{n_pools}: {pool_names}")
                result = run_series(
                    pool, n_games,
                    on_game_complete=dashboard.update if dashboard else None,
                )
                if dashboard:
                    dashboard.on_series_complete(f"L1 Pool {i + 1}", result)
                wins.update(result.wins)
            print(format_results(wins, n_games))
        else:
            print(f"[run] {tier}: {len(players)} players, {n_games} games …")
            result = run_series(
                players, n_games, tier=tier,
                on_game_complete=dashboard.update if dashboard else None,
            )
            if dashboard:
                dashboard.on_series_complete(f"{tier} Tier", result)
            wins = result.wins
            print(format_results(wins, n_games))

        movements = apply_season_results(wins, n_games, tier, top_n, path=lb_path)
        for m in movements:
            print(f"  {m}")
        print(f"[done] {tier}: leaderboard updated.")
        tier_results[tier] = wins

    relegations = settle_relegations(tier_results, top_n, path=lb_path)
    if relegations:
        print("[settle] cross-tier relegations:")
        for m in relegations:
            print(f"  {m}")

    return tier_results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run one season step in-process (simulation mode, no GitHub API)."
    )
    parser.add_argument(
        "date",
        nargs="?",
        default=None,
        help="Date override (YYYY-MM-DD). Sets TODAY env var. Default: system date.",
    )
    parser.add_argument(
        "--n-games",
        type=int,
        default=int(os.environ.get("N_GAMES", "1000")),
        help="Games per tier/pool. Default: N_GAMES env var or 1000.",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=int(os.environ.get("TOP_N", "4")),
        help="League capacity per PRM/CH tier. Default: TOP_N env var or 4.",
    )
    parser.add_argument(
        "--dashboard-players",
        default=None,
        help='Comma-separated player names to watch, e.g. "Oracle,EvilStewie".',
    )
    args = parser.parse_args()

    if args.date:
        os.environ["TODAY"] = args.date

    lb_path = os.environ.get("LEADERBOARD_PATH", "leaderboard.yaml")
    top_n = args.top_n

    watched = (
        [n.strip() for n in args.dashboard_players.split(",")]
        if args.dashboard_players
        else None
    )

    if watched:
        from game.dashboard import Dashboard
        dashboard = Dashboard(watched=watched, n_games=args.n_games)
    else:
        dashboard = None

    with (dashboard or nullcontext()):
        run_season(args.n_games, top_n, lb_path, dashboard=dashboard)


if __name__ == "__main__":
    main()
```

- [ ] **Step 5.4: Run smoke test**

```bash
just pytest tests/test_main.py::test_simulation_season_run_season
```

Expected: PASS

- [ ] **Step 5.5: Run full test suite**

```bash
just pytest-all
```

Expected: all pass.

- [ ] **Step 5.6: Commit**

```bash
git add game/simulation/season.py tests/test_main.py
git commit -m "$(cat <<'EOF'
feat(sim): add in-process season simulation with dashboard support

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: `game/simulation/tournament.py` — in-process tournament simulation

**Files:**

- Create: `game/simulation/tournament.py`
- Test: `tests/test_main.py`

**Interfaces:**

- Consumes: `run_series` (Task 2), `Dashboard` (Task 4)
- Consumes: `form_pools`, `_load_lb`, `_save_lb`, `current_quarter`, `next_tournament_monday` from `game.season.utils`
- Consumes: `get_tier_players`, `tier_capacities` from `game.components.leaderboard`
- Produces: `run_tournament(n_games, lb_path, players_dir=None, dashboard=None) -> dict[str, dict[str, int]]`
- Produces: `main()` — CLI entry point with `--date`, `--n-games`, `--dashboard-players`

The function: zeros tier_stats, seeds players by tier+win%, forms pools, runs each pool in-process, assigns placements. Returns `{pool_key: wins}`.

- [ ] **Step 6.1: Write failing smoke test**

Add to `tests/test_main.py`:

```python
def test_simulation_tournament_run_tournament(tmp_path):
    """run_tournament runs pool games and assigns placements."""
    import textwrap
    import yaml
    from game.simulation.tournament import run_tournament

    lb = {
        "players": {
            "AliceBot": {"tier": "L1", "tier_stats": {}, "tier_since": "2026-01-01T00:00:00Z"},
            "BrunoBot": {"tier": "L1", "tier_stats": {}, "tier_since": "2026-01-01T00:00:00Z"},
            "CleoBot":  {"tier": "CH", "tier_stats": {}, "tier_since": "2026-01-01T00:00:00Z"},
            "DaveBot":  {"tier": "PRM", "tier_stats": {}, "tier_since": "2026-01-01T00:00:00Z"},
        },
        "tournament_state": {},
    }
    lb_path = str(tmp_path / "leaderboard.yaml")
    with open(lb_path, "w") as f:
        yaml.dump(lb, f)

    players_dir = tmp_path / "players"
    players_dir.mkdir()
    for name in ("AliceBot", "BrunoBot", "CleoBot", "DaveBot"):
        (players_dir / f"{name.lower()}.py").write_text(textwrap.dedent(f"""
            from game.components.bets import Bet
            class {name}:
                name = "{name}"
                def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):
                    if prior_bet is None:
                        return Bet(1, 2, self.name)
                    return None
        """))
    (players_dir / "__init__.py").write_text("")

    pool_results = run_tournament(
        n_games=5, lb_path=lb_path, players_dir=str(players_dir)
    )
    assert len(pool_results) >= 1
    # After assignment, all players should have a tier
    import yaml
    with open(lb_path) as f:
        data = yaml.safe_load(f)
    tiers = {p["tier"] for p in data["players"].values()}
    assert tiers <= {"PRM", "CH", "L1", "DED", "inactive"}
```

- [ ] **Step 6.2: Run test to confirm it fails**

```bash
just pytest tests/test_main.py::test_simulation_tournament_run_tournament
```

Expected: FAIL — `ModuleNotFoundError: No module named 'game.simulation.tournament'`

- [ ] **Step 6.3: Create `game/simulation/tournament.py`**

```python
"""In-process tournament simulation for local bot tuning.

Replaces the subprocess-based approach of reset_season.py for simulation use cases.
Does not create GitHub issues — DRY_RUN-safe by design.
"""
from __future__ import annotations

import argparse
import math
import os
from contextlib import nullcontext
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent.parent


def run_tournament(
    n_games: int,
    lb_path: str,
    players_dir: str | None = None,
    dashboard=None,
) -> dict[str, dict[str, int]]:
    """Run a full tournament in-process. Returns {pool_key: {player: win_count}}.

    Zeroes tier_stats, seeds players by prior tier+win%, forms pools,
    runs each pool's games, then assigns placements top-down.

    Args:
        n_games: Games per pool.
        lb_path: Path to leaderboard.yaml.
        players_dir: Path to players/ directory. Defaults to repo root / players.
        dashboard: Optional Dashboard instance for live display.
    """
    from game.components.leaderboard import get_tier_players, tier_capacities
    from game.components.series import format_results, run_series
    from game.components.utils import apply_display_names, import_player_classes_from_dir
    from game.season.utils import _load_lb, _save_lb, current_quarter, form_pools

    if players_dir is None:
        players_dir = str(_REPO_ROOT / "players")

    data = _load_lb(lb_path)
    quarter = current_quarter()

    # Compute seeding order BEFORE zeroing tier_stats
    tier_order_seed = ["PRM", "CH", "L1", "DED", "inactive"]
    players_data = data.get("players", {})

    def _win_pct(name: str) -> float:
        ts = players_data.get(name, {}).get("tier_stats", {})
        total_w = sum(t.get("wins", 0) for t in ts.values())
        total_g = sum(t.get("games", 0) for t in ts.values())
        return total_w / total_g if total_g else 0.0

    seeded: list[str] = []
    for tier in tier_order_seed:
        in_tier = get_tier_players(data, tier)
        in_tier.sort(key=_win_pct, reverse=True)
        seeded.extend(in_tier)

    # Zero tier_stats for the new quarter
    for player in data.get("players", {}).values():
        player["tier_stats"] = {}
    data.setdefault("tournament_state", {})
    data["tournament_state"]["quarter"] = quarter
    _save_lb(data, lb_path)
    print(f"[done] zero_stats: all tier_stats cleared for {quarter}")

    # Form pools
    n_players = len(seeded)
    n_pools = max(1, math.ceil(n_players / 8))
    pools = form_pools(seeded, n_pools)

    # Load player classes
    all_players = import_player_classes_from_dir(players_dir)
    apply_display_names(all_players, data.get("players", {}))
    players_by_name = {type(p).__name__: p for p in all_players}

    pool_results: dict[str, dict[str, int]] = {}

    for i, pool_names in enumerate(pools):
        key = f"pool_{i}"
        pool = [players_by_name[n] for n in pool_names if n in players_by_name]
        if len(pool) < 2:
            print(f"[skip] {key}: {len(pool)} player(s) — need ≥ 2.")
            continue
        print(f"[run] {key}: {pool_names}")
        result = run_series(
            pool, n_games,
            on_game_complete=dashboard.update if dashboard else None,
        )
        if dashboard:
            dashboard.on_series_complete(key, result)
        pool_results[key] = result.wins
        print(format_results(result.wins, n_games))
        print(f"[done] {key}: {result.wins}")

    # Assign placements
    _assign_placements(lb_path, pool_results)
    return pool_results


def _assign_placements(lb_path: str, pool_results: dict[str, dict[str, int]]) -> None:
    """Assign tier placements from pool results, top-down by total win count."""
    from game.components.leaderboard import tier_capacities
    from game.season.utils import _load_lb, _save_lb

    data = _load_lb(lb_path)
    all_wins: dict[str, int] = {}
    for wins in pool_results.values():
        all_wins.update(wins)

    ranked = [name for name, _ in sorted(all_wins.items(), key=lambda x: -x[1])]
    n_players = len(data.get("players", {}))
    caps = tier_capacities(n_players)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    idx = 0
    players = data.get("players", {})
    for tier in ("PRM", "CH", "L1", "DED"):
        cap = caps.get(tier, 0)
        for _ in range(cap):
            if idx >= len(ranked):
                break
            name = ranked[idx]
            if name in players:
                players[name]["tier"] = tier
                players[name]["tier_since"] = now
            idx += 1

    data["tournament_state"]["pool_results"] = pool_results
    _save_lb(data, lb_path)
    print(f"[done] assign_placements: {n_players} players placed")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run tournament in-process (simulation mode, no GitHub API)."
    )
    parser.add_argument(
        "--date",
        default=None,
        help="Date override (YYYY-MM-DD). Sets TODAY env var.",
    )
    parser.add_argument(
        "--n-games",
        type=int,
        default=int(os.environ.get("N_GAMES", "1000")),
        help="Games per pool. Default: N_GAMES env var or 1000.",
    )
    parser.add_argument(
        "--dashboard-players",
        default=None,
        help='Comma-separated player names to watch, e.g. "Oracle,EvilStewie".',
    )
    args = parser.parse_args()

    if args.date:
        os.environ["TODAY"] = args.date

    lb_path = os.environ.get("LEADERBOARD_PATH", "leaderboard.yaml")

    watched = (
        [n.strip() for n in args.dashboard_players.split(",")]
        if args.dashboard_players
        else None
    )

    if watched:
        from game.dashboard import Dashboard
        dashboard = Dashboard(watched=watched, n_games=args.n_games)
    else:
        dashboard = None

    with (dashboard or nullcontext()):
        run_tournament(args.n_games, lb_path, dashboard=dashboard)


if __name__ == "__main__":
    main()
```

- [ ] **Step 6.4: Run smoke test**

```bash
just pytest tests/test_main.py::test_simulation_tournament_run_tournament
```

Expected: PASS

- [ ] **Step 6.5: Run full test suite**

```bash
just pytest-all
```

Expected: all pass.

- [ ] **Step 6.6: Commit**

```bash
git add game/simulation/tournament.py tests/test_main.py
git commit -m "$(cat <<'EOF'
feat(sim): add in-process tournament simulation with dashboard support

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: Update `game/simulation/quarter.py` for dashboard + in-process execution

**Files:**

- Modify: `game/simulation/quarter.py`

The quarter sim currently calls `run_season.py`/`reset_season.py` via subprocess using `run_step()`. This prevents the dashboard from aggregating across Mondays (cross-process boundary). We switch to calling `game.simulation.season.run_season` and `game.simulation.tournament.run_tournament` in-process, then capture their stdout for the report using `contextlib.redirect_stdout`.

The dashboard writes to `Console(stderr=True)` (see Task 4), so it is not captured by `redirect_stdout` — it goes to the real terminal even during stdout capture.

**Interfaces:**

- Consumes: `run_season` from `game.simulation.season` (Task 5)
- Consumes: `run_tournament` from `game.simulation.tournament` (Task 6)
- Consumes: `Dashboard` from `game.dashboard` (Task 4)

- [ ] **Step 7.1: Replace `run_step` and update `main` in `game/simulation/quarter.py`**

Replace the `run_step` function and the `main` function. Keep `compute_mondays`, `write_report`, `_format_output`, `parse_args` unchanged.

**Update the import block at the top of the file.** Remove `import subprocess` and `from io import StringIO` (no longer needed). Add `from contextlib import nullcontext`.

Before:

```python
import argparse
import os
import subprocess
import time
from datetime import date, datetime, timedelta
from io import StringIO
from pathlib import Path
```

After:

```python
import argparse
import os
import time
from contextlib import nullcontext
from datetime import date, datetime, timedelta
from pathlib import Path
```

Find and replace the `run_step` function (the one that calls `subprocess.Popen`):

```python
def run_step(
    step_date: date,
    mode: str,
    n_games: int,
    lb_path: str,
    dashboard=None,
) -> str:
    """Run one Monday step in-process. Returns captured stdout text for the report.

    Dashboard writes to Console(stderr=True) so it reaches the terminal even
    while stdout is redirected here for report capture.
    """
    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        if mode == "tournament":
            from game.simulation.tournament import run_tournament
            run_tournament(n_games=n_games, lb_path=lb_path, dashboard=dashboard)
        else:
            from game.simulation.season import run_season
            run_season(
                n_games=n_games,
                top_n=int(os.environ.get("TOP_N", "4")),
                lb_path=lb_path,
                dashboard=dashboard,
            )
    output = buf.getvalue()
    print(output, end="")
    return output
```

Update `parse_args` to add `--dashboard-players`:

```python
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Simulate a full quarter locally (DRY_RUN=true, no GitHub changes)."
    )
    parser.add_argument(
        "--start",
        type=lambda s: date.fromisoformat(s),
        default=next_tournament_monday(),
        help="Tournament Monday to start from (YYYY-MM-DD). Default: next upcoming.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Report output path. Default: sim-YYYY-QN.md in current directory.",
    )
    parser.add_argument(
        "--n-games",
        type=int,
        default=int(os.environ.get("N_GAMES", "1000")),
        help="Games per tier/pool per run. Default: N_GAMES env var or 1000.",
    )
    parser.add_argument(
        "--dashboard-players",
        default=None,
        help='Comma-separated player names to watch live, e.g. "Oracle,EvilStewie".',
    )
    return parser.parse_args()
```

Update `main` to create and thread the dashboard:

```python
def main() -> None:
    args = parse_args()

    import sys

    from game.season.utils import is_tournament_monday

    if not is_tournament_monday(args.start):
        print(
            f"[error] {args.start} is not a tournament Monday "
            "(must be the first Monday of Jan/Apr/Jul/Oct).",
            file=sys.stderr,
        )
        sys.exit(1)

    quarter = current_quarter(args.start)
    output_file = args.output or Path(f"sim-{quarter}.md")
    lb_path = os.environ.get("LEADERBOARD_PATH", "leaderboard.yaml")

    watched = (
        [n.strip() for n in args.dashboard_players.split(",")]
        if args.dashboard_players
        else None
    )

    mondays = compute_mondays(args.start)
    print(f"[simulate] {quarter}: {len(mondays)} Mondays, {args.n_games} games/run")
    print(f"[simulate] leaderboard: {lb_path}")
    print(f"[simulate] report: {output_file}")
    print(
        f"[simulate] WARNING: {lb_path} will be modified in place. "
        f"Use `git checkout -- {lb_path}` or `just clean` to restore."
    )
    print()

    if watched:
        from game.dashboard import Dashboard
        dashboard = Dashboard(watched=watched, n_games=args.n_games)
    else:
        dashboard = None

    steps: list[dict] = []
    t_total = time.perf_counter()

    with (dashboard or nullcontext()):
        for i, (step_date, mode) in enumerate(mondays):
            label = "Tournament" if mode == "tournament" else "season"
            print(f"{'=' * 60}")
            print(f"[simulate] {step_date} — {label} (week {i + 1}/{len(mondays)})")
            print(f"{'=' * 60}")
            os.environ["TODAY"] = step_date.isoformat()
            t0 = time.perf_counter()
            output = run_step(step_date, mode, args.n_games, lb_path, dashboard=dashboard)
            elapsed = time.perf_counter() - t0
            print(f"[simulate] done in {elapsed:.1f}s")
            steps.append({"date": step_date, "mode": mode, "output": output})
            print()

    write_report(steps, lb_path, output_file, args.n_games)
    print(f"[simulate] total elapsed: {time.perf_counter() - t_total:.1f}s")
```

Also add `nullcontext` to the imports at the top of the file:

```python
from contextlib import nullcontext
```

- [ ] **Step 7.2: Verify quarter sim runs without dashboard**

First, find the next valid tournament Monday:

```bash
uv run python -c "from game.season.utils import next_tournament_monday; print(next_tournament_monday())"
```

Then run a quick smoke test (replace DATE with the output above):

```bash
DRY_RUN=true N_GAMES=5 uv run python -m game.simulation.quarter --start DATE
```

Expected: runs without error, produces `sim-YYYY-QN.md`, prints step outputs. Exit 0.

- [ ] **Step 7.3: Run full test suite**

```bash
just pytest-all
```

Expected: all pass.

- [ ] **Step 7.4: Commit**

```bash
git add game/simulation/quarter.py
git commit -m "$(cat <<'EOF'
feat(sim): switch quarter sim to in-process execution with dashboard threading

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 8: Justfile and CLI wiring

**Files:**

- Modify: `.Justfile`

Update `simulate-season` and `simulate-tournament` to call the new Python modules, and add `*ARGS` passthrough to all three recipes.

- [ ] **Step 8.1: Update `.Justfile`**

Replace the three existing simulate-\* recipes:

```makefile
# Simulate a season run (dry run). Optional date and extra args.
# Usage: just simulate-season
#        just simulate-season 2026-07-13
#        just simulate-season 2026-07-13 --dashboard-players Oracle,EvilStewie
[group('algorithms')]
simulate-season *ARGS:
    DRY_RUN=1 uv run python -m game.simulation.season {{ARGS}}

# Simulate the next tournament (dry run). Finds the next quarterly Monday automatically.
# Usage: just simulate-tournament
#        just simulate-tournament --dashboard-players Oracle
[group('algorithms')]
simulate-tournament *ARGS:
    DRY_RUN=1 uv run python -m game.simulation.tournament {{ARGS}}

# Simulate a full quarter: tournament + all regular Mondays. Writes sim-YYYY-QN.md.
# Usage: just simulate-quarter
#        just simulate-quarter 2026-07-06
#        just simulate-quarter 2026-07-06 500
#        just simulate-quarter 2026-07-06 500 --dashboard-players Oracle,EvilStewie
[group('algorithms')]
simulate-quarter start='' n-games='' *ARGS:
    uv run python -m game.simulation.quarter \
        $([ -n "{{start}}" ] && echo "--start {{start}}") \
        $([ -n "{{n-games}}" ] && echo "--n-games {{n-games}}") \
        {{ARGS}}
```

`simulate-season` accepts an optional positional date as its first arg — see Task 5's `main()`. Passing `2026-07-13` still works. `simulate-quarter` keeps the positional `start` and `n-games` params for backward compatibility; `--dashboard-players` is passed via `*ARGS`.

- [ ] **Step 8.2: Verify simulate-season works with a date arg**

```bash
N_GAMES=5 just simulate-season 2026-07-13
```

Expected: runs games for each eligible tier, updates `leaderboard.yaml`, prints results. Exit 0.

- [ ] **Step 8.3: Verify simulate-tournament works**

```bash
N_GAMES=5 just simulate-tournament
```

Expected: zeroes tier_stats, runs pool games, assigns placements. Exit 0.

- [ ] **Step 8.4: Verify dashboard flag is accepted (no crash)**

```bash
N_GAMES=5 just simulate-season 2026-07-13 --dashboard-players DoesNotExist
```

Expected: runs without crash. Dashboard shows nothing meaningful for a non-existent player but doesn't error.

- [ ] **Step 8.5: Commit**

```bash
git add .Justfile
git commit -m "$(cat <<'EOF'
feat(sim): update Justfile to call in-process simulation modules with *ARGS passthrough

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Self-Review Checklist

Before opening the PR, verify:

1. **Spec coverage:**
   - [x] `GameStats` new counters (Task 1) — die-loss, call-accuracy, rounds, games, penalties
   - [x] `record_penalty` method (Task 1) + calls in `game_orchestrator` (Task 3)
   - [x] `SeriesResult` dataclass (Task 2)
   - [x] `run_series` new signature with `capture_outcomes` before `on_game_complete` (Task 2)
   - [x] `Dashboard` class with two-panel layout (Task 4)
   - [x] Terminal height clipping + CPU optimization (Task 4 `__init__`)
   - [x] `PlayerAggregate` for right-panel accumulation (Task 4)
   - [x] `--dashboard-players` CLI arg on all three sim scripts (Tasks 5, 6, 7)
   - [x] `*ARGS` passthrough in Justfile recipes (Task 8)
   - [x] `rich` in `pyproject.toml` (Task 4)

2. **Caller updates:**
   - `game/__main__.py` unpacks `result.wins` (Task 2, Step 2.4)
   - Existing tests in `tests/test_main.py` that call `run_series` still pass because they don't unpack the return value — only tests that used `wins = run_series(...)` need updating, and those are covered by `just pytest-all`

3. **`simulate-quarter` backward compat:** The recipe retains the positional `start` and `n-games` params so existing usage (`just simulate-quarter 2026-07-06 500`) continues to work. `*ARGS` captures anything after those two positionals, allowing `--dashboard-players` to be appended.

4. **DRY_RUN:** `game/simulation/season.py` and `game/simulation/tournament.py` are DRY_RUN-safe by design — they never call GitHub APIs regardless of `DRY_RUN`. The `.Justfile` passes `DRY_RUN=1` for the two single-step recipes as documentation, but it has no effect on the new code.
