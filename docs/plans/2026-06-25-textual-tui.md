# Textual TUI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `game/dashboard.py` (rich.Live) with a full Textual TUI that provides tab-per-series navigation, any-player drill-down, scrollable log, and cumulative stats across a quarter simulation.

**Architecture:** `TuiAdapter` is the sole public interface — callers pass it as `dashboard=` to existing simulation functions unchanged. The Textual app runs in the main thread (blocking via `app.run()`); the simulation runs in a background thread started from `LiarsDiceApp.on_mount()` after a `threading.Event` signals the app is ready. All cross-thread communication goes through `call_from_thread → post_message` with typed Message subclasses.

**Tech Stack:** `textual>=1.0`, `rich` (already present), Python 3.11+, standard `threading`/`copy`/`sys`.

## Global Constraints

- Always use `uv run python` — never bare `python3` or `python`
- Test runner: `just pytest-all` (runs `tests/` and `examples/tests/`)
- All commits must pass commitlint: type must be in `type-enum`, scope (if used) must be in `scope-enum` — check `.commitlintrc.mjs` before committing
- `PlayerAggregate` fields must exactly match the existing `dashboard.py` dataclass (same field names and types) — callers rely on this
- `TuiAdapter` public API: `__init__(n_games)`, `run(sim_callable)`, `start_series(label)`, `update(game_num, wins, stats)`, `on_series_complete(label, result)` — these are called by simulation scripts unchanged
- `resolve_player_names(names, lb_path, players_dir) → list[str]` must keep this exact signature
- Branch: `feat/textual-tui`
- Co-author footer: `🤖 Co-Authored with [Claude Code](https://claude.com/claude-code)`

---

### Task 1: Package scaffolding, textual dependency, and message types

Add `textual` to project dependencies and create the `game/tui/` package with all typed message classes.

**Files:**

- Modify: `pyproject.toml` (add textual dependency)
- Create: `game/tui/__init__.py` (stub — populated in Task 5)
- Create: `game/tui/messages.py`
- Create: `tests/test_tui_messages.py`

**Interfaces:**

- Consumes: nothing
- Produces:
  - `SeriesStarted(label: str)` — Message
  - `GameComplete(game_num: int, wins: dict[str, int], stats: GameStats)` — Message
  - `SeriesComplete(label: str, result: SeriesResult)` — Message
  - `SimulationComplete()` — Message
  - `LogLine(text: str)` — Message
  - `DrillInPlayer(player: str)` — Message (posted by StandingsWidget → handled by LiarsDiceApp)

- [ ] **Step 1: Add textual to pyproject.toml**

In `pyproject.toml`, change:

```toml
dependencies = ["pandas", "pyyaml", "rich"]
```

to:

```toml
dependencies = ["pandas", "pyyaml", "rich", "textual>=1.0"]
```

- [ ] **Step 2: Install the new dependency**

```bash
uv sync
```

Expected: textual and its dependencies (anyio, etc.) install without error.

- [ ] **Step 3: Create the package stub**

Create `game/tui/__init__.py`:

```python
"""Textual TUI for live bot tuning during simulation runs."""
```

- [ ] **Step 4: Write the failing test**

Create `tests/test_tui_messages.py`:

```python
def test_series_started_fields():
    from game.tui.messages import SeriesStarted
    msg = SeriesStarted("Pool 0")
    assert msg.label == "Pool 0"


def test_game_complete_fields():
    from game.tui.messages import GameComplete
    from game.components.stats import GameStats
    stats = GameStats()
    msg = GameComplete(42, {"Oracle": 20, "EvilStewie": 10}, stats)
    assert msg.game_num == 42
    assert msg.wins["Oracle"] == 20
    assert msg.stats is stats


def test_series_complete_fields():
    from game.tui.messages import SeriesComplete
    from game.components.series import SeriesResult
    from game.components.stats import GameStats
    result = SeriesResult(wins={"Oracle": 500}, stats=GameStats())
    msg = SeriesComplete("CH Tier", result)
    assert msg.label == "CH Tier"
    assert msg.result is result


def test_simulation_complete_no_fields():
    from game.tui.messages import SimulationComplete
    msg = SimulationComplete()
    assert msg is not None


def test_log_line_fields():
    from game.tui.messages import LogLine
    msg = LogLine("[run] Pool 0: starting")
    assert msg.text == "[run] Pool 0: starting"


def test_drill_in_player_fields():
    from game.tui.messages import DrillInPlayer
    msg = DrillInPlayer("Oracle")
    assert msg.player == "Oracle"
```

- [ ] **Step 5: Run test to verify it fails**

```bash
just pytest tests/test_tui_messages.py
```

Expected: FAIL — `ModuleNotFoundError: No module named 'game.tui.messages'`

- [ ] **Step 6: Create game/tui/messages.py**

```python
"""Typed Textual message classes for TUI ↔ simulation thread communication."""

from __future__ import annotations

from textual.message import Message


class SeriesStarted(Message):
    def __init__(self, label: str) -> None:
        super().__init__()
        self.label = label


class GameComplete(Message):
    def __init__(self, game_num: int, wins: dict[str, int], stats) -> None:
        super().__init__()
        self.game_num = game_num
        self.wins = wins
        self.stats = stats


class SeriesComplete(Message):
    def __init__(self, label: str, result) -> None:
        super().__init__()
        self.label = label
        self.result = result


class SimulationComplete(Message):
    pass


class LogLine(Message):
    def __init__(self, text: str) -> None:
        super().__init__()
        self.text = text


class DrillInPlayer(Message):
    def __init__(self, player: str) -> None:
        super().__init__()
        self.player = player
```

- [ ] **Step 7: Run test to verify it passes**

```bash
just pytest tests/test_tui_messages.py
```

Expected: 6 passed.

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml game/tui/__init__.py game/tui/messages.py tests/test_tui_messages.py
git commit -m "feat(engine): add game/tui package with typed message classes

🤖 Co-Authored with [Claude Code](https://claude.com/claude-code)"
```

---

### Task 2: Data types and pure render functions

Move `PlayerAggregate`, helper utilities, render functions, `_build_display_aggregate`, and `LogStream` from `game/dashboard.py` into `game/tui/widgets.py` with standalone (non-method) signatures. These are pure Python functions with no Textual dependency — fully testable.

**Files:**

- Create: `game/tui/widgets.py`
- Create: `tests/test_tui_render.py`

**Interfaces:**

- Consumes: `game/tui/messages.py` (none yet — render functions are standalone)
- Produces:
  - `PlayerAggregate` dataclass (same fields as in `dashboard.py`)
  - `_bar(value: float, total: float, width: int = 20) -> str`
  - `_pct(num: int, den: int) -> str`
  - `_render_left(player, game_num, n_games, wins, stats) -> str`
  - `_render_right(player, agg: PlayerAggregate) -> str`
  - `_build_display_aggregate(player, baseline, current_wins, current_stats) -> PlayerAggregate`
  - `LogStream(app)` class with `write(text)` and `flush()` methods

- [ ] **Step 1: Write the failing tests**

Create `tests/test_tui_render.py`:

```python
import pytest
from unittest.mock import MagicMock


def _make_stats(player: str, games: int = 100, wins: int = 40):
    """Create a minimal GameStats-like object for testing."""
    from game.components.stats import GameStats
    s = GameStats()
    # Manually set internal state for the fields render functions read
    s._games_played[player] = games
    s._rounds_played[player] = games * 10
    s._penalty_count[player] = 2
    s._die_losses_from_bluff[player]["EvilStewie"] = 15
    s._die_losses_from_challenge[player]["EvilStewie"] = 12
    s._challenge_success_by_face[player][1] = 7
    s._challenge_count_by_face[player][1] = 10
    return s


def test_bar_empty_when_total_zero():
    from game.tui.widgets import _bar
    result = _bar(0, 0)
    assert "░" in result
    assert "█" not in result


def test_bar_full_when_value_equals_total():
    from game.tui.widgets import _bar
    result = _bar(10, 10, width=5)
    assert result == "█████"


def test_bar_half():
    from game.tui.widgets import _bar
    result = _bar(5, 10, width=10)
    assert result.count("█") == 5
    assert result.count("░") == 5


def test_pct_zero_denominator():
    from game.tui.widgets import _pct
    assert _pct(0, 0) == "—"


def test_pct_half():
    from game.tui.widgets import _pct
    assert _pct(1, 2) == "50.0%"


def test_render_left_returns_string():
    from game.tui.widgets import _render_left
    stats = _make_stats("Oracle")
    result = _render_left("Oracle", 50, 100, {"Oracle": 20, "EvilStewie": 30}, stats)
    assert isinstance(result, str)
    assert "Win Rate" in result
    assert "Die Losses" in result
    assert "Call Accuracy" in result


def test_render_right_returns_string():
    from game.tui.widgets import _render_right, PlayerAggregate
    agg = PlayerAggregate(total_games=100, wins=40)
    result = _render_right("Oracle", agg)
    assert isinstance(result, str)
    assert "Win Rate" in result
    assert "40.0%" in result


def test_player_aggregate_defaults():
    from game.tui.widgets import PlayerAggregate
    agg = PlayerAggregate()
    assert agg.total_games == 0
    assert agg.wins == 0
    assert agg.die_losses_from_bluff == {}
    assert agg.challenge_success_by_face == {}


def test_build_display_aggregate_no_stats():
    from game.tui.widgets import PlayerAggregate, _build_display_aggregate
    baseline = PlayerAggregate(total_games=500, wins=200)
    result = _build_display_aggregate("Oracle", baseline, {}, None)
    assert result.total_games == 500
    assert result.wins == 200


def test_build_display_aggregate_adds_live():
    from game.tui.widgets import PlayerAggregate, _build_display_aggregate
    baseline = PlayerAggregate(total_games=500, wins=200)
    stats = _make_stats("Oracle", games=100, wins=0)
    result = _build_display_aggregate("Oracle", baseline, {"Oracle": 40}, stats)
    assert result.total_games == 600
    assert result.wins == 240
```

- [ ] **Step 2: Run test to verify it fails**

```bash
just pytest tests/test_tui_render.py
```

Expected: FAIL — `ModuleNotFoundError: No module named 'game.tui.widgets'`

- [ ] **Step 3: Create game/tui/widgets.py with data types and render functions**

```python
"""Data types, render helpers, and Textual widgets for the liars-dice TUI."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field

_BAR_W = 20
_OVERVIEW_BAR_W = 12
_BAR_FULL = "█"
_BAR_EMPTY = "░"
PANEL_HEIGHT = 18


@dataclass
class PlayerAggregate:
    """Cumulative stats for the Sim Total panel, accumulated across series."""

    total_games: int = 0
    wins: int = 0
    die_losses_from_bluff: dict[str, int] = field(default_factory=dict)
    die_losses_from_challenge: dict[str, int] = field(default_factory=dict)
    die_wins_from_bluff: dict[str, int] = field(default_factory=dict)
    die_wins_from_challenge: dict[str, int] = field(default_factory=dict)
    rounds_played: int = 0
    penalties: int = 0
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
        set(bluff_losses)
        | set(call_losses)
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
        lines.append(f"  {opp:<12}  {lb:>3}/{lc:<3}    {wb:>3}/{wc:<3}  {sign}{net}")

    cs_by_face = stats.challenge_success_by_face.get(player, {})
    cc_by_face = stats.challenge_count_by_face.get(player, {})
    total_cs = sum(cs_by_face.values())
    total_cc = sum(cc_by_face.values())
    face_str = "  ".join(
        f"{f}:{_pct(cs_by_face.get(f, 0), cc_by_face.get(f, 0))}" for f in range(1, 7)
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
        set(agg.die_losses_from_bluff)
        | set(agg.die_losses_from_challenge)
        | set(agg.die_wins_from_bluff)
        | set(agg.die_wins_from_challenge)
    )
    for opp in opponents[:5]:
        lb = agg.die_losses_from_bluff.get(opp, 0)
        lc = agg.die_losses_from_challenge.get(opp, 0)
        wb = agg.die_wins_from_bluff.get(opp, 0)
        wc = agg.die_wins_from_challenge.get(opp, 0)
        net = (wb + wc) - (lb + lc)
        sign = "+" if net >= 0 else ""
        lines.append(f"  {opp:<12}  {lb:>3}/{lc:<3}    {wb:>3}/{wc:<3}  {sign}{net}")

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


def _build_display_aggregate(
    player: str,
    baseline: PlayerAggregate,
    current_wins: dict[str, int],
    current_stats,
) -> PlayerAggregate:
    """Merge completed-series baseline with live current-series stats."""
    if current_stats is None:
        return baseline

    bl = baseline
    stats = current_stats

    def _merge(base: dict, live: dict) -> dict:
        result = dict(base)
        for k, v in live.items():
            result[k] = result.get(k, 0) + v
        return result

    return PlayerAggregate(
        total_games=bl.total_games + stats.games_played.get(player, 0),
        wins=bl.wins + current_wins.get(player, 0),
        rounds_played=bl.rounds_played + stats.rounds_played.get(player, 0),
        penalties=bl.penalties + stats.penalty_count.get(player, 0),
        die_losses_from_bluff=_merge(
            bl.die_losses_from_bluff, stats.die_losses_from_bluff.get(player, {})
        ),
        die_losses_from_challenge=_merge(
            bl.die_losses_from_challenge, stats.die_losses_from_challenge.get(player, {})
        ),
        die_wins_from_bluff=_merge(
            bl.die_wins_from_bluff,
            {
                opp: d.get(player, 0)
                for opp, d in stats.die_losses_from_bluff.items()
                if opp != player and player in d
            },
        ),
        die_wins_from_challenge=_merge(
            bl.die_wins_from_challenge,
            {
                opp: d.get(player, 0)
                for opp, d in stats.die_losses_from_challenge.items()
                if opp != player and player in d
            },
        ),
        challenge_success_by_face=_merge(
            bl.challenge_success_by_face, stats.challenge_success_by_face.get(player, {})
        ),
        challenge_total_by_face=_merge(
            bl.challenge_total_by_face, stats.challenge_count_by_face.get(player, {})
        ),
    )


class LogStream:
    """Replaces sys.stdout during simulation; routes print() to the TUI log panel."""

    def __init__(self, app: "LiarsDiceApp") -> None:  # noqa: F821
        self._app = app

    def write(self, text: str) -> None:
        if text.strip():
            from game.tui.messages import LogLine
            self._app.call_from_thread(self._app.post_message, LogLine(text.rstrip()))

    def flush(self) -> None:
        pass
```

- [ ] **Step 4: Run test to verify it passes**

```bash
just pytest tests/test_tui_render.py
```

Expected: 10 passed.

- [ ] **Step 5: Run full suite to confirm nothing broken**

```bash
just pytest-all
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add game/tui/widgets.py tests/test_tui_render.py
git commit -m "feat(engine): add TUI data types and pure render functions

🤖 Co-Authored with [Claude Code](https://claude.com/claude-code)"
```

---

### Task 3: Textual widget classes

Add `StandingsWidget`, `PlayerStatsPanel`, and `LogPanel` to `game/tui/widgets.py`. These are the visual building blocks — no tests needed here since they require a running Textual event loop; correctness is verified in the Task 5 smoke test.

**Files:**

- Modify: `game/tui/widgets.py` (append widget classes)

**Interfaces:**

- Consumes: `PlayerAggregate`, `_bar`, `_pct`, `_render_left`, `_render_right`, `_build_display_aggregate` from Task 2; `DrillInPlayer` from `game/tui/messages.py`
- Produces:
  - `StandingsWidget(Widget)` with `update_standings(wins, stats, game_num, n_games, series_label)` and `clear_standings()`
  - `PlayerStatsPanel(Static)` with `.player: str`, `update_data(wins, stats, game_num)`, `update_baseline(baseline: PlayerAggregate)`
  - `LogPanel(RichLog)` with `write_line(text)`, `toggle_verbose()`, `.verbose: bool`

- [ ] **Step 1: Append Textual widget classes to game/tui/widgets.py**

Add these imports at the top of `game/tui/widgets.py` (after existing imports):

```python
from rich.columns import Columns
from rich.panel import Panel
from rich.text import Text
from textual.widget import Widget
from textual.widgets import RichLog, Static
```

Then append these classes at the bottom of `game/tui/widgets.py`:

```python
class StandingsWidget(Widget):
    """Cursor-navigable standings table for the current series."""

    BINDINGS = [
        ("up", "cursor_up", "Up"),
        ("down", "cursor_down", "Down"),
        ("enter", "drill_in", "Drill In"),
    ]

    DEFAULT_CSS = """
    StandingsWidget {
        height: auto;
        max-height: 15;
        border: solid $primary-darken-2;
        padding: 0 1;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._players: list[str] = []
        self._wins: dict[str, int] = {}
        self._stats = None
        self._game_num = 0
        self._n_games = 0
        self._series_label = ""
        self._cursor = 0

    def update_standings(
        self,
        wins: dict[str, int],
        stats,
        game_num: int,
        n_games: int,
        series_label: str = "",
    ) -> None:
        self._wins = wins
        self._stats = stats
        self._game_num = game_num
        self._n_games = n_games
        self._series_label = series_label
        self._players = sorted(wins.keys(), key=lambda p: -wins.get(p, 0))
        self._cursor = min(self._cursor, max(0, len(self._players) - 1))
        self.refresh()

    def clear_standings(self) -> None:
        self._players = []
        self._wins = {}
        self._stats = None
        self._game_num = 0
        self.refresh()

    def render(self) -> Text:
        if not self._players:
            return Text("Waiting for simulation to start…", style="dim")
        title = f"  {self._series_label} — Game {self._game_num}/{self._n_games}\n"
        t = Text(title, style="bold")
        max_wins = max((self._wins.get(p, 0) for p in self._players), default=1) or 1
        for i, player in enumerate(self._players):
            w = self._wins.get(player, 0)
            gp = (self._stats.games_played.get(player, 1) if self._stats else 1) or 1
            bar = _bar(w, max_wins, width=_OVERVIEW_BAR_W)
            line = f"  {player:<14}  {w:>5}  {_pct(w, gp):>6}  {bar}\n"
            style = "bold reverse" if i == self._cursor else ""
            t.append(line, style=style)
        return t

    def action_cursor_up(self) -> None:
        self._cursor = max(0, self._cursor - 1)
        self.refresh()

    def action_cursor_down(self) -> None:
        self._cursor = min(len(self._players) - 1, self._cursor + 1)
        self.refresh()

    def action_drill_in(self) -> None:
        if self._players:
            from game.tui.messages import DrillInPlayer
            self.post_message(DrillInPlayer(self._players[self._cursor]))


class PlayerStatsPanel(Static):
    """Two-column stats panel for one drilled player. Right column hidden when baseline is empty."""

    DEFAULT_CSS = """
    PlayerStatsPanel {
        height: auto;
        margin-bottom: 1;
    }
    """

    def __init__(self, player: str, n_games: int, baseline: PlayerAggregate) -> None:
        super().__init__("")
        self.player = player
        self._n_games = n_games
        self._baseline = baseline
        self._current_wins: dict[str, int] = {}
        self._current_stats = None
        self._game_num = 0

    def update_data(self, wins: dict[str, int], stats, game_num: int) -> None:
        self._current_wins = wins
        self._current_stats = stats
        self._game_num = game_num
        self.update(self._build_renderable())

    def update_baseline(self, baseline: PlayerAggregate) -> None:
        self._baseline = baseline
        self.update(self._build_renderable())

    def _build_renderable(self):
        left_title = f"{self.player}: This Week — Game {self._game_num}/{self._n_games}"
        if self._current_stats is not None:
            left_body = _render_left(
                self.player,
                self._game_num,
                self._n_games,
                self._current_wins,
                self._current_stats,
            )
        else:
            left_body = "Waiting for first game…"

        show_right = self._baseline.total_games > 0
        if show_right:
            display_agg = _build_display_aggregate(
                self.player, self._baseline, self._current_wins, self._current_stats
            )
            right_title = f"{self.player}: Sim Total — {display_agg.total_games:,} games"
            right_body = _render_right(self.player, display_agg)
            return Columns(
                [Panel(left_body, title=left_title), Panel(right_body, title=right_title)]
            )
        return Panel(left_body, title=left_title)


class LogPanel(RichLog):
    """Scrollable log panel, always visible at the bottom of the screen."""

    DEFAULT_CSS = """
    LogPanel {
        height: 10;
        border-top: solid $primary-darken-2;
    }
    """

    def __init__(self) -> None:
        super().__init__(highlight=True, markup=True, wrap=True)
        self._verbose = False

    @property
    def verbose(self) -> bool:
        return self._verbose

    def toggle_verbose(self) -> None:
        self._verbose = not self._verbose
        status = "on" if self._verbose else "off"
        self.write(f"[dim]verbose mode {status}[/dim]")

    def write_line(self, text: str) -> None:
        self.write(text)
```

- [ ] **Step 2: Run full suite to confirm no import errors**

```bash
just pytest-all
```

Expected: all tests pass (widget classes don't run without an event loop, so no new test failures).

- [ ] **Step 3: Commit**

```bash
git add game/tui/widgets.py
git commit -m "feat(engine): add Textual widget classes for TUI

🤖 Co-Authored with [Claude Code](https://claude.com/claude-code)"
```

---

### Task 4: LiarsDiceApp

Create `game/tui/app.py` with the full Textual app: layout, CSS, keybindings, message handlers for all five message types, PlayerAggregate accumulation logic (ported from `dashboard.py`'s `on_series_complete` method), and history tab creation.

**Files:**

- Create: `game/tui/app.py`

**Interfaces:**

- Consumes:
  - `StandingsWidget`, `PlayerStatsPanel`, `LogPanel`, `PlayerAggregate`, `_build_display_aggregate` from `game/tui/widgets.py`
  - All message classes from `game/tui/messages.py`
- Produces:
  - `LiarsDiceApp(App)` — constructed as `LiarsDiceApp(n_games, ready_event)` where `ready_event: threading.Event`

- [ ] **Step 1: Create game/tui/app.py**

```python
"""Textual app for the liars-dice live tuning dashboard."""

from __future__ import annotations

import copy
import threading

from textual.app import App, ComposeResult
from textual.containers import ScrollableContainer
from textual.widgets import Static, TabbedContent, TabPane

from game.tui.messages import (
    DrillInPlayer,
    GameComplete,
    LogLine,
    SeriesComplete,
    SeriesStarted,
    SimulationComplete,
)
from game.tui.widgets import (
    LogPanel,
    PlayerAggregate,
    PlayerStatsPanel,
    StandingsWidget,
    _OVERVIEW_BAR_W,
    _bar,
    _pct,
)


class LiarsDiceApp(App):
    """Textual TUI for live bot tuning. Receives messages from the simulation thread."""

    CSS = """
    Screen {
        layout: vertical;
    }

    TabbedContent {
        height: 1fr;
    }

    TabPane {
        layout: vertical;
        padding: 0;
    }

    StandingsWidget {
        height: auto;
        max-height: 15;
    }

    #player-panels {
        height: 1fr;
    }

    LogPanel {
        height: 10;
        dock: bottom;
    }
    """

    BINDINGS = [
        ("q", "quit_when_done", "Quit"),
        ("v", "toggle_verbose", "Verbose"),
        ("escape", "remove_panel", "Remove panel"),
    ]

    def __init__(self, n_games: int, ready_event: threading.Event) -> None:
        super().__init__()
        self._n_games = n_games
        self._ready_event = ready_event
        self._aggregates: dict[str, PlayerAggregate] = {}
        self._series_baseline: dict[str, PlayerAggregate] = {}
        self._current_wins: dict[str, int] = {}
        self._current_stats = None
        self._current_game = 0
        self._current_label = ""
        self._sim_done = False
        self._drilled: list[str] = []
        self._history_tab_count = 0

    def compose(self) -> ComposeResult:
        with TabbedContent(id="tabs", initial="live"):
            with TabPane("Live", id="live"):
                yield StandingsWidget(id="standings")
                yield ScrollableContainer(id="player-panels")
        yield LogPanel(id="log")

    def on_mount(self) -> None:
        self._ready_event.set()

    # ── Message handlers ──────────────────────────────────────────────────

    def on_series_started(self, message: SeriesStarted) -> None:
        self._current_label = message.label
        self._current_wins = {}
        self._current_stats = None
        self._current_game = 0
        standings = self.query_one("#standings", StandingsWidget)
        standings.clear_standings()
        log = self.query_one(LogPanel)
        log.write_line(f"[bold]── {message.label} ──[/bold]")

    def on_game_complete(self, message: GameComplete) -> None:
        self._current_game = message.game_num
        self._current_wins = message.wins
        self._current_stats = message.stats

        if message.game_num == 1:
            for player in self._aggregates:
                self._series_baseline[player] = copy.deepcopy(self._aggregates[player])
            for player in message.wins:
                if player not in self._series_baseline:
                    self._series_baseline[player] = PlayerAggregate()

        standings = self.query_one("#standings", StandingsWidget)
        standings.update_standings(
            message.wins,
            message.stats,
            message.game_num,
            self._n_games,
            self._current_label,
        )

        for panel in self.query(PlayerStatsPanel):
            baseline = self._series_baseline.get(panel.player, PlayerAggregate())
            panel.update_baseline(baseline)
            panel.update_data(message.wins, message.stats, message.game_num)

        log = self.query_one(LogPanel)
        if log.verbose:
            winner = max(message.wins, key=lambda p: message.wins.get(p, 0), default="?")
            log.write_line(
                f"[dim]game {message.game_num}: {winner} leads "
                f"({message.wins.get(winner, 0)} wins)[/dim]"
            )

    def on_series_complete(self, message: SeriesComplete) -> None:
        self._accumulate(message.result)
        self._add_history_tab(message.label, message.result)

    def on_simulation_complete(self, _: SimulationComplete) -> None:
        self._sim_done = True
        log = self.query_one(LogPanel)
        log.write_line("[bold green]Simulation complete — press q to exit[/bold green]")

    def on_log_line(self, message: LogLine) -> None:
        self.query_one(LogPanel).write_line(message.text)

    def on_drill_in_player(self, message: DrillInPlayer) -> None:
        if message.player in self._drilled:
            return
        self._drilled.append(message.player)
        baseline = self._series_baseline.get(message.player, PlayerAggregate())
        panel = PlayerStatsPanel(
            player=message.player,
            n_games=self._n_games,
            baseline=baseline,
        )
        if self._current_stats is not None:
            panel.update_data(self._current_wins, self._current_stats, self._current_game)
        container = self.query_one("#player-panels", ScrollableContainer)
        container.mount(panel)

    # ── Actions ───────────────────────────────────────────────────────────

    def action_quit_when_done(self) -> None:
        if self._sim_done:
            self.exit()

    def action_toggle_verbose(self) -> None:
        self.query_one(LogPanel).toggle_verbose()

    def action_remove_panel(self) -> None:
        if not self._drilled:
            return
        player = self._drilled.pop()
        for panel in self.query(PlayerStatsPanel):
            if panel.player == player:
                panel.remove()
                return

    # ── Internal helpers ──────────────────────────────────────────────────

    def _accumulate(self, result) -> None:
        """Accumulate SeriesResult into running PlayerAggregate totals."""
        stats = result.stats
        for player in stats.games_played:
            if player not in self._aggregates:
                self._aggregates[player] = PlayerAggregate()
            agg = self._aggregates[player]
            w = result.wins.get(player, 0)
            gp = stats.games_played.get(player, 0)
            agg.total_games += gp
            agg.wins += w
            agg.rounds_played += stats.rounds_played.get(player, 0)
            agg.penalties += stats.penalty_count.get(player, 0)

            for opp, count in stats.die_losses_from_bluff.get(player, {}).items():
                agg.die_losses_from_bluff[opp] = (
                    agg.die_losses_from_bluff.get(opp, 0) + count
                )
            for opp, count in stats.die_losses_from_challenge.get(player, {}).items():
                agg.die_losses_from_challenge[opp] = (
                    agg.die_losses_from_challenge.get(opp, 0) + count
                )

            bluff_wins = stats.die_losses_from_bluff
            call_wins = stats.die_losses_from_challenge
            for opp in stats.games_played:
                if opp == player:
                    continue
                wb = bluff_wins.get(opp, {}).get(player, 0)
                wc = call_wins.get(opp, {}).get(player, 0)
                if wb:
                    agg.die_wins_from_bluff[opp] = (
                        agg.die_wins_from_bluff.get(opp, 0) + wb
                    )
                if wc:
                    agg.die_wins_from_challenge[opp] = (
                        agg.die_wins_from_challenge.get(opp, 0) + wc
                    )

            for face in range(1, 7):
                cs = stats.challenge_success_by_face.get(player, {}).get(face, 0)
                cc = stats.challenge_count_by_face.get(player, {}).get(face, 0)
                agg.challenge_success_by_face[face] = (
                    agg.challenge_success_by_face.get(face, 0) + cs
                )
                agg.challenge_total_by_face[face] = (
                    agg.challenge_total_by_face.get(face, 0) + cc
                )

    def _add_history_tab(self, label: str, result) -> None:
        """Add a read-only history tab with the final series standings."""
        self._history_tab_count += 1
        tab_id = f"hist-{self._history_tab_count}"
        wins = result.wins
        stats = result.stats
        players_sorted = sorted(wins, key=lambda p: -wins.get(p, 0))
        max_wins = max(wins.values(), default=1) or 1
        lines = [f"  Final standings — {label}\n"]
        for p in players_sorted:
            w = wins.get(p, 0)
            gp = stats.games_played.get(p, 1) or 1
                lines.append(
                f"  {p:<14}  {w:>5}  {_pct(w, gp):>6}  {_bar(w, max_wins, width=_OVERVIEW_BAR_W)}\n"
            )
        content = Static("".join(lines))
        tabs = self.query_one(TabbedContent)
        tabs.add_pane(TabPane(label, content, id=tab_id))
```

- [ ] **Step 2: Run full suite to confirm no import errors**

```bash
just pytest-all
```

Expected: all tests pass.

- [ ] **Step 3: Commit**

```bash
git add game/tui/app.py
git commit -m "feat(engine): add LiarsDiceApp with message handlers and accumulation

🤖 Co-Authored with [Claude Code](https://claude.com/claude-code)"
```

---

### Task 5: TuiAdapter and resolve_player_names

Populate `game/tui/__init__.py` with `TuiAdapter` and `resolve_player_names`. `TuiAdapter.run()` starts the Textual app in the main thread, spawns the simulation in a background thread, and uses a `threading.Event` to ensure messages are only sent after the app is ready. Add unit tests for the parts that don't require a running event loop.

**Files:**

- Modify: `game/tui/__init__.py` (replace stub)
- Create: `tests/test_tui.py`

**Interfaces:**

- Consumes:
  - `LiarsDiceApp` from `game/tui/app.py`
  - `LogStream` from `game/tui/widgets.py`
  - All messages from `game/tui/messages.py`
- Produces:
  - `TuiAdapter(n_games: int)` with `.run(sim: Callable[[], None])`, `.start_series(label)`, `.update(game_num, wins, stats)`, `.on_series_complete(label, result)`
  - `resolve_player_names(names: list[str], lb_path: str, players_dir: str) -> list[str]`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_tui.py`:

```python
def test_tuiadapter_init():
    from game.tui import TuiAdapter
    adapter = TuiAdapter(n_games=100)
    assert adapter._n_games == 100
    assert adapter._app is None


def test_resolve_player_names_passthrough_unknown():
    """Names not matching any class name are returned unchanged."""
    from game.tui import resolve_player_names
    import os
    lb_path = os.environ.get("LEADERBOARD_PATH", "leaderboard.yaml")
    result = resolve_player_names(["Nonexistent"], lb_path, "players")
    assert result == ["Nonexistent"]


def test_resolve_player_names_display_name_passthrough():
    """Display names that don't match a class name are returned unchanged."""
    from game.tui import resolve_player_names
    import os
    lb_path = os.environ.get("LEADERBOARD_PATH", "leaderboard.yaml")
    result = resolve_player_names(["Oracle"], lb_path, "players")
    # "Oracle" is a display name, not a class name — returned as-is
    assert "Oracle" in result
```

- [ ] **Step 2: Run test to verify it fails**

```bash
just pytest tests/test_tui.py
```

Expected: FAIL — `ImportError` or attribute errors since `__init__.py` is just a stub.

- [ ] **Step 3: Populate game/tui/**init**.py**

```python
"""Textual TUI for live bot tuning during simulation runs."""

from __future__ import annotations

import sys
import threading
from collections.abc import Callable

from game.tui.app import LiarsDiceApp
from game.tui.messages import GameComplete, SeriesComplete, SeriesStarted, SimulationComplete
from game.tui.widgets import LogStream


def resolve_player_names(names: list[str], lb_path: str, players_dir: str) -> list[str]:
    """Map class names to display names so --tui works with either form."""
    from game.components.utils import apply_display_names, import_player_classes_from_dir
    from game.season.utils import _load_lb

    all_players = import_player_classes_from_dir(players_dir)
    apply_display_names(all_players, _load_lb(lb_path).get("players", {}))
    name_map = {type(p).__name__: p.name for p in all_players}
    return [name_map.get(n, n) for n in names]


class TuiAdapter:
    """Public interface for the TUI — matches the Dashboard API used by simulation callers."""

    def __init__(self, n_games: int) -> None:
        self._n_games = n_games
        self._app: LiarsDiceApp | None = None

    def run(self, simulation: Callable[[], None]) -> None:
        """Start the TUI. Runs simulation in a background thread; blocks until user quits."""
        ready = threading.Event()
        self._app = LiarsDiceApp(n_games=self._n_games, ready_event=ready)

        original_stdout = sys.stdout
        log_stream = LogStream(self._app)

        def _sim_thread() -> None:
            ready.wait()
            sys.stdout = log_stream
            try:
                simulation()
            finally:
                sys.stdout = original_stdout
                self._app.call_from_thread(
                    self._app.post_message, SimulationComplete()
                )

        t = threading.Thread(target=_sim_thread, daemon=True)
        t.start()
        self._app.run()

    def start_series(self, label: str) -> None:
        if self._app:
            self._app.call_from_thread(self._app.post_message, SeriesStarted(label))

    def update(self, game_num: int, wins: dict[str, int], stats) -> None:
        if self._app:
            self._app.call_from_thread(
                self._app.post_message, GameComplete(game_num, wins, stats)
            )

    def on_series_complete(self, label: str, result) -> None:
        if self._app:
            self._app.call_from_thread(
                self._app.post_message, SeriesComplete(label, result)
            )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
just pytest tests/test_tui.py
```

Expected: 3 passed.

- [ ] **Step 5: Run full suite**

```bash
just pytest-all
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add game/tui/__init__.py tests/test_tui.py
git commit -m "feat(engine): add TuiAdapter and resolve_player_names

🤖 Co-Authored with [Claude Code](https://claude.com/claude-code)"
```

---

### Task 6: Update simulation callers, delete dashboard.py, and update Justfile

Wire the three simulation scripts to `TuiAdapter`, remove the old `--dashboard-players` flag, replace it with `--tui`, delete `game/dashboard.py`, and update the Justfile comments to reflect the new flag.

**Files:**

- Delete: `game/dashboard.py`
- Modify: `game/simulation/season.py`
- Modify: `game/simulation/tournament.py`
- Modify: `game/simulation/quarter.py`
- Modify: `.Justfile`

**Interfaces:**

- Consumes: `TuiAdapter` from `game/tui/__init__.py`
- Produces: updated CLI for all three simulation scripts with `--tui` flag

- [ ] **Step 1: Update game/simulation/tournament.py**

In `main()`, replace the `watched`/`Dashboard` block with:

```python
    if args.tui:
        from game.tui import TuiAdapter
        adapter = TuiAdapter(n_games=args.n_games)
        adapter.run(lambda: run_tournament(args.n_games, lb_path, dashboard=adapter))
    else:
        run_tournament(args.n_games, lb_path)
```

Replace the `--dashboard-players` argument with:

```python
    parser.add_argument(
        "--tui",
        action="store_true",
        default=False,
        help="Launch the Textual TUI dashboard.",
    )
```

Remove the lines that imported `Dashboard`, `resolve_player_names`, and the `nullcontext` import (check if `nullcontext` is still used elsewhere in the file; remove only if not).

The updated `main()` in full:

```python
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
        "--tui",
        action="store_true",
        default=False,
        help="Launch the Textual TUI dashboard.",
    )
    args = parser.parse_args()

    if args.date:
        os.environ["TODAY"] = args.date

    lb_path = os.environ.get("LEADERBOARD_PATH", "leaderboard.yaml")

    if args.tui:
        from game.tui import TuiAdapter
        adapter = TuiAdapter(n_games=args.n_games)
        adapter.run(lambda: run_tournament(args.n_games, lb_path, dashboard=adapter))
    else:
        run_tournament(args.n_games, lb_path)
```

Also remove `from contextlib import nullcontext` if it is no longer used.

- [ ] **Step 2: Update game/simulation/season.py**

Same pattern. Remove `--dashboard-players` and `nullcontext`. Replace with `--tui`. The updated `main()`:

```python
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
        "--tui",
        action="store_true",
        default=False,
        help="Launch the Textual TUI dashboard.",
    )
    args = parser.parse_args()

    if args.date:
        os.environ["TODAY"] = args.date

    lb_path = os.environ.get("LEADERBOARD_PATH", "leaderboard.yaml")
    top_n = args.top_n

    if args.tui:
        from game.tui import TuiAdapter
        adapter = TuiAdapter(n_games=args.n_games)
        adapter.run(lambda: run_season(args.n_games, top_n, lb_path, dashboard=adapter))
    else:
        run_season(args.n_games, top_n, lb_path)
```

- [ ] **Step 3: Update game/simulation/quarter.py**

In `main()`, replace the `watched`/`Dashboard` block:

```python
    if watched:
        from game.dashboard import Dashboard, resolve_player_names
        watched = resolve_player_names(watched, lb_path, str(_REPO_ROOT / "players"))
        dashboard = Dashboard(watched=watched, n_games=args.n_games)
    else:
        dashboard = None

    steps: list[dict] = []
    t_total = time.perf_counter()

    with dashboard or nullcontext():
        for i, (step_date, mode) in enumerate(mondays):
            ...
            output = run_step(step_date, mode, args.n_games, lb_path, dashboard=dashboard)
```

Replace with:

```python
    steps: list[dict] = []
    t_total = time.perf_counter()

    if args.tui:
        from game.tui import TuiAdapter
        adapter: TuiAdapter | None = TuiAdapter(n_games=args.n_games)

        def _run_quarter() -> None:
            for i, (step_date, mode) in enumerate(mondays):
                label = "Tournament" if mode == "tournament" else "season"
                print(f"{'=' * 60}")
                print(f"[simulate] {step_date} — {label} (week {i + 1}/{len(mondays)})")
                print(f"{'=' * 60}")
                os.environ["TODAY"] = step_date.isoformat()
                t0 = time.perf_counter()
                output = run_step(step_date, mode, args.n_games, lb_path, dashboard=adapter)
                elapsed = time.perf_counter() - t0
                print(f"[simulate] done in {elapsed:.1f}s")
                steps.append({"date": step_date, "mode": mode, "output": output})
                print()

        adapter.run(_run_quarter)
    else:
        for i, (step_date, mode) in enumerate(mondays):
            label = "Tournament" if mode == "tournament" else "season"
            print(f"{'=' * 60}")
            print(f"[simulate] {step_date} — {label} (week {i + 1}/{len(mondays)})")
            print(f"{'=' * 60}")
            os.environ["TODAY"] = step_date.isoformat()
            t0 = time.perf_counter()
            output = run_step(step_date, mode, args.n_games, lb_path, dashboard=None)
            elapsed = time.perf_counter() - t0
            print(f"[simulate] done in {elapsed:.1f}s")
            steps.append({"date": step_date, "mode": mode, "output": output})
            print()
```

Replace the `--dashboard-players` argument in `parse_args()` with:

```python
    parser.add_argument(
        "--tui",
        action="store_true",
        default=False,
        help="Launch the Textual TUI dashboard.",
    )
```

Remove `from contextlib import nullcontext` if no longer used.

- [ ] **Step 4: Delete game/dashboard.py**

```bash
git rm game/dashboard.py
```

- [ ] **Step 5: Update Justfile comments**

In `.Justfile`, find the `simulate-season`, `simulate-tournament`, and `simulate-quarter` recipe comment blocks and update the usage examples from `--dashboard-players Oracle` to `--tui`:

```
# Usage: just simulate-season
#        just simulate-season 2026-07-13
#        just simulate-season 2026-07-13 --tui
```

```
# Usage: just simulate-tournament
#        just simulate-tournament --tui
```

```
# Usage: just simulate-quarter
#        just simulate-quarter 2026-07-06
#        just simulate-quarter 2026-07-06 500
#        just simulate-quarter 2026-07-06 500 --tui
```

- [ ] **Step 6: Run full test suite**

```bash
just pytest-all
```

Expected: all tests pass. Confirm no remaining imports of `game.dashboard`:

```bash
grep -r "game.dashboard\|from game import dashboard\|import dashboard" game/ tests/ .github/ 2>/dev/null
```

Expected: no output.

- [ ] **Step 7: Commit**

```bash
git add game/simulation/season.py game/simulation/tournament.py game/simulation/quarter.py .Justfile
# game/dashboard.py deletion was already staged by `git rm` in Step 4
git commit -m "feat(game): replace Dashboard with TuiAdapter in simulation callers

Removes --dashboard-players flag, adds --tui flag to all three
simulation scripts. Deletes game/dashboard.py.

🤖 Co-Authored with [Claude Code](https://claude.com/claude-code)"
```
