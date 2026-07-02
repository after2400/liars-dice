# Player Performance Instrumentation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Instrument the game engine to measure per-player wall-clock time, CPU time, and (opt-in) peak memory during `algo()` calls, surfaced only in local simulation reports (`simulate-season`, `simulate-quarter`, `simulate-tournament`).

**Architecture:** A new engine-internal `PerfTracker` class (`game/components/perf.py`) wraps each `player.algo()` call inside `game_orchestrator()`. `run_series()` forwards it through and returns it on `SeriesResult.perf`. The three in-process simulation entry points (`season.py`, `tournament.py`, `quarter.py`) create one tracker per run, thread a `--profile-memory` CLI flag into it, and print a `format_perf()` table — which lands in the Markdown report automatically via the existing stdout-capture pipeline. Production CI (`.github/scripts/run_season.py` → `game/__main__.py` subprocess) is never touched, so this has zero effect on the live Monday run.

**Tech Stack:** Python 3.11+ stdlib only (`time.perf_counter`, `time.thread_time`, `tracemalloc`) — no new dependencies. `uv run pytest` / `just pytest*`.

**Note on the spec:** the design doc (`docs/specs/2026-07-01-player-perf-instrumentation-design.md`) sketches `format_perf()` living in `game/components/perf.py`. This plan places it in `game/components/series.py` instead, next to `format_results()` — both `season.py` and `tournament.py` already do `from game.components.series import format_results, run_series`, so colocating keeps one import site instead of two. No behavior change, just file organization.

## Global Constraints

- Always use `uv run python` / `just pytest*` — never bare `python`/`pytest` (CLAUDE.md).
- Engine-level change: run `just pytest-all` (not just `just pytest-players`) before every commit in this plan.
- No new dependencies — `time` and `tracemalloc` are stdlib.
- `time.thread_time()` must be used for CPU time (not `time.process_time()`) — isolates the main game-loop thread from the Textual TUI's background render thread. Supported on Linux, macOS, Windows.
- Commit messages: read `.commitlintrc.mjs` types/scopes before writing. This plan's commits are all `feat(game): ...` or `test(game): ...` scoped to the engine.
- Every commit trailer: `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>`.
- `PerfTracker` is never passed into a player's `algo()` — no change to the AST import allowlist in `game/validate.py`.
- `.github/scripts/run_season.py` and `game/__main__.py` are out of scope — do not modify them in this plan.

---

## Task 1: `PerfTracker` core class

**Files:**

- Create: `game/components/perf.py`
- Create: `tests/test_perf.py`

**Interfaces:**

- Produces: `PerfTracker(profile_memory: bool = False)`, `.time_call(player_name: str)` (context manager), `.tracked_players -> list[str]`, `.call_count(name) -> int`, `.avg_wall_ms(name) -> float`, `.p95_wall_ms(name) -> float`, `.max_wall_ms(name) -> float`, `.avg_cpu_ms(name) -> float`, `.max_cpu_ms(name) -> float`, `.avg_peak_kb(name) -> float | None`, `.max_peak_kb(name) -> float | None`, `.profile_memory: bool` (public attribute).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_perf.py`:

```python
import pytest


def test_unknown_player_has_zero_defaults():
    from game.components.perf import PerfTracker

    tracker = PerfTracker()
    assert tracker.call_count("Nobody") == 0
    assert tracker.avg_wall_ms("Nobody") == 0.0
    assert tracker.max_wall_ms("Nobody") == 0.0
    assert tracker.p95_wall_ms("Nobody") == 0.0
    assert tracker.avg_cpu_ms("Nobody") == 0.0
    assert tracker.max_cpu_ms("Nobody") == 0.0


def test_tracked_players_empty_for_new_tracker():
    from game.components.perf import PerfTracker

    assert PerfTracker().tracked_players == []


def test_time_call_records_one_sample(monkeypatch):
    import game.components.perf as perf_mod

    wall = iter([0.0, 0.010])
    cpu = iter([0.0, 0.004])
    monkeypatch.setattr(perf_mod.time, "perf_counter", lambda: next(wall))
    monkeypatch.setattr(perf_mod.time, "thread_time", lambda: next(cpu))

    tracker = perf_mod.PerfTracker()
    with tracker.time_call("Alice"):
        pass

    assert tracker.call_count("Alice") == 1
    assert tracker.tracked_players == ["Alice"]
    assert tracker.avg_wall_ms("Alice") == pytest.approx(10.0)
    assert tracker.avg_cpu_ms("Alice") == pytest.approx(4.0)


def test_time_call_records_sample_even_when_body_raises(monkeypatch):
    import game.components.perf as perf_mod

    wall = iter([0.0, 0.005])
    cpu = iter([0.0, 0.002])
    monkeypatch.setattr(perf_mod.time, "perf_counter", lambda: next(wall))
    monkeypatch.setattr(perf_mod.time, "thread_time", lambda: next(cpu))

    tracker = perf_mod.PerfTracker()
    with pytest.raises(RuntimeError):
        with tracker.time_call("Crasher"):
            raise RuntimeError("boom")

    assert tracker.call_count("Crasher") == 1
    assert tracker.avg_wall_ms("Crasher") == pytest.approx(5.0)


def test_avg_and_max_wall_ms_across_three_calls(monkeypatch):
    import game.components.perf as perf_mod

    # elapsed per call: 10ms, 20ms, 30ms
    wall = iter([0.000, 0.010, 0.010, 0.030, 0.030, 0.060])
    cpu = iter([0.0] * 6)
    monkeypatch.setattr(perf_mod.time, "perf_counter", lambda: next(wall))
    monkeypatch.setattr(perf_mod.time, "thread_time", lambda: next(cpu))

    tracker = perf_mod.PerfTracker()
    for _ in range(3):
        with tracker.time_call("Bruno"):
            pass

    assert tracker.call_count("Bruno") == 3
    assert tracker.avg_wall_ms("Bruno") == pytest.approx(20.0)
    assert tracker.max_wall_ms("Bruno") == pytest.approx(30.0)


def test_p95_wall_ms_nearest_rank(monkeypatch):
    import game.components.perf as perf_mod

    # 20 calls with elapsed 1ms..20ms
    wall = iter([v for k in range(1, 21) for v in (0.0, k * 0.001)])
    cpu = iter([0.0] * 40)
    monkeypatch.setattr(perf_mod.time, "perf_counter", lambda: next(wall))
    monkeypatch.setattr(perf_mod.time, "thread_time", lambda: next(cpu))

    tracker = perf_mod.PerfTracker()
    for _ in range(20):
        with tracker.time_call("Carol"):
            pass

    assert tracker.p95_wall_ms("Carol") == pytest.approx(19.0)
    assert tracker.max_wall_ms("Carol") == pytest.approx(20.0)
    assert tracker.avg_wall_ms("Carol") == pytest.approx(sum(range(1, 21)) / 20)


def test_peak_memory_none_when_profiling_disabled():
    from game.components.perf import PerfTracker

    tracker = PerfTracker()  # profile_memory defaults to False
    with tracker.time_call("Alice"):
        pass

    assert tracker.avg_peak_kb("Alice") is None
    assert tracker.max_peak_kb("Alice") is None


def test_peak_memory_recorded_when_profiling_enabled():
    from game.components.perf import PerfTracker

    tracker = PerfTracker(profile_memory=True)
    with tracker.time_call("Allocator"):
        _ = [0] * 200_000  # list's own backing array is well above any noise floor

    avg_kb = tracker.avg_peak_kb("Allocator")
    assert avg_kb is not None
    assert avg_kb > 50  # generous floor; real allocation is ~1.6MB
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `just pytest tests/test_perf.py -v`
Expected: `ModuleNotFoundError: No module named 'game.components.perf'`

- [ ] **Step 3: Implement `game/components/perf.py`**

```python
"""Engine-internal per-player CPU/wall-time and (optional) memory instrumentation.

PerfTracker is never passed into a player's algo() — it's read only by
simulation callers (game/simulation/*.py), so no change to the AST import
allowlist in game/validate.py is needed.
"""

import math
import time
import tracemalloc
from collections import defaultdict
from contextlib import contextmanager


class PerfTracker:
    """Records per-player wall-clock time, CPU time, and (opt-in) peak memory.

    Pass `profile_memory=True` to also track tracemalloc peak-allocation bytes
    per call — this has real overhead, so it defaults to off.
    """

    def __init__(self, profile_memory: bool = False) -> None:
        self.profile_memory = profile_memory
        self._wall: dict[str, list[float]] = defaultdict(list)
        self._cpu: dict[str, list[float]] = defaultdict(list)
        self._peak_kb: dict[str, list[float]] = defaultdict(list)
        if profile_memory and not tracemalloc.is_tracing():
            tracemalloc.start()

    @contextmanager
    def time_call(self, player_name: str):
        """Times one algo() call. Records a sample even if the wrapped code
        raises — the finally block always runs before the exception propagates."""
        if self.profile_memory:
            tracemalloc.reset_peak()
        t0_wall = time.perf_counter()
        t0_cpu = time.thread_time()
        try:
            yield
        finally:
            self._wall[player_name].append(time.perf_counter() - t0_wall)
            self._cpu[player_name].append(time.thread_time() - t0_cpu)
            if self.profile_memory:
                _, peak = tracemalloc.get_traced_memory()
                self._peak_kb[player_name].append(peak / 1024)

    @property
    def tracked_players(self) -> list[str]:
        return sorted(self._wall.keys())

    def call_count(self, player_name: str) -> int:
        return len(self._wall.get(player_name, []))

    def avg_wall_ms(self, player_name: str) -> float:
        samples = self._wall.get(player_name, [])
        return (sum(samples) / len(samples) * 1000) if samples else 0.0

    def p95_wall_ms(self, player_name: str) -> float:
        return self._percentile_ms(self._wall.get(player_name, []), 0.95)

    def max_wall_ms(self, player_name: str) -> float:
        samples = self._wall.get(player_name, [])
        return max(samples) * 1000 if samples else 0.0

    def avg_cpu_ms(self, player_name: str) -> float:
        samples = self._cpu.get(player_name, [])
        return (sum(samples) / len(samples) * 1000) if samples else 0.0

    def max_cpu_ms(self, player_name: str) -> float:
        samples = self._cpu.get(player_name, [])
        return max(samples) * 1000 if samples else 0.0

    def avg_peak_kb(self, player_name: str) -> float | None:
        if not self.profile_memory:
            return None
        samples = self._peak_kb.get(player_name, [])
        return (sum(samples) / len(samples)) if samples else None

    def max_peak_kb(self, player_name: str) -> float | None:
        if not self.profile_memory:
            return None
        samples = self._peak_kb.get(player_name, [])
        return max(samples) if samples else None

    @staticmethod
    def _percentile_ms(samples: list[float], p: float) -> float:
        if not samples:
            return 0.0
        ordered = sorted(samples)
        idx = min(len(ordered) - 1, math.ceil(p * len(ordered)) - 1)
        return ordered[idx] * 1000
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `just pytest tests/test_perf.py -v`
Expected: all 9 tests pass.

- [ ] **Step 5: Run full suite to check for regressions**

Run: `just pytest-all`
Expected: all existing tests plus the 9 new ones pass.

- [ ] **Step 6: Commit**

```bash
git add game/components/perf.py tests/test_perf.py
git commit -m "$(cat <<'EOF'
feat(game): add PerfTracker for per-player wall/CPU/memory timing

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: `format_perf()` formatter

**Files:**

- Modify: `game/components/series.py`
- Modify: `tests/test_perf.py`

**Interfaces:**

- Consumes: `PerfTracker` from Task 1 (`.tracked_players`, `.profile_memory`, `.call_count`, `.avg_wall_ms`, `.p95_wall_ms`, `.max_wall_ms`, `.avg_cpu_ms`, `.max_cpu_ms`, `.avg_peak_kb`, `.max_peak_kb`).
- Produces: `format_perf(tracker: PerfTracker, n_games: int) -> str`, importable as `from game.components.series import format_perf`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_perf.py`:

```python
def test_format_perf_empty_tracker_returns_empty_string():
    from game.components.perf import PerfTracker
    from game.components.series import format_perf

    assert format_perf(PerfTracker(), n_games=10) == ""


def test_format_perf_includes_all_tracked_players(monkeypatch):
    import game.components.perf as perf_mod
    from game.components.series import format_perf

    wall = iter([0.0, 0.010, 0.0, 0.020])
    cpu = iter([0.0] * 4)
    monkeypatch.setattr(perf_mod.time, "perf_counter", lambda: next(wall))
    monkeypatch.setattr(perf_mod.time, "thread_time", lambda: next(cpu))

    tracker = perf_mod.PerfTracker()
    with tracker.time_call("Alice"):
        pass
    with tracker.time_call("Bruno"):
        pass

    output = format_perf(tracker, n_games=5)
    assert "Alice" in output
    assert "Bruno" in output
    assert "Player Performance" in output


def test_format_perf_sorts_slowest_first(monkeypatch):
    import game.components.perf as perf_mod
    from game.components.series import format_perf

    # Alice: 10ms, Bruno: 30ms
    wall = iter([0.0, 0.010, 0.0, 0.030])
    cpu = iter([0.0] * 4)
    monkeypatch.setattr(perf_mod.time, "perf_counter", lambda: next(wall))
    monkeypatch.setattr(perf_mod.time, "thread_time", lambda: next(cpu))

    tracker = perf_mod.PerfTracker()
    with tracker.time_call("Alice"):
        pass
    with tracker.time_call("Bruno"):
        pass

    output = format_perf(tracker, n_games=5)
    assert output.index("Bruno") < output.index("Alice")


def test_format_perf_omits_memory_columns_when_disabled(monkeypatch):
    import game.components.perf as perf_mod
    from game.components.series import format_perf

    monkeypatch.setattr(perf_mod.time, "perf_counter", lambda: 0.0)
    monkeypatch.setattr(perf_mod.time, "thread_time", lambda: 0.0)

    tracker = perf_mod.PerfTracker(profile_memory=False)
    with tracker.time_call("Alice"):
        pass

    assert "Peak" not in format_perf(tracker, n_games=1)


def test_format_perf_includes_memory_columns_when_enabled():
    from game.components.perf import PerfTracker
    from game.components.series import format_perf

    tracker = PerfTracker(profile_memory=True)
    with tracker.time_call("Alice"):
        _ = [0] * 1000

    assert "Peak" in format_perf(tracker, n_games=1)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `just pytest tests/test_perf.py -v`
Expected: `ImportError: cannot import name 'format_perf' from 'game.components.series'`

- [ ] **Step 3: Modify `game/components/series.py`**

Change the import block at the top of the file:

```python
import logging
import secrets
from collections.abc import Callable
from dataclasses import dataclass

from game.components.perf import PerfTracker
from game.components.stats import GameStats

logger = logging.getLogger(__name__)
```

Append this function at the end of the file, after `format_results()`:

```python
def format_perf(tracker: PerfTracker, n_games: int) -> str:
    """Formats a PerfTracker's per-player timing (and optional memory) stats as a table.

    Sorted slowest-first (by avg wall time) so outliers are easy to spot.
    Returns "" if no calls were recorded.
    """
    players = tracker.tracked_players
    if not players:
        return ""

    name_w = max(len(n) for n in players) + 2
    memory_on = tracker.profile_memory

    headers = [
        "Player",
        "Calls",
        "AvgWall(ms)",
        "P95Wall(ms)",
        "MaxWall(ms)",
        "AvgCPU(ms)",
        "MaxCPU(ms)",
    ]
    widths = [name_w, 7, 12, 12, 12, 11, 11]
    if memory_on:
        headers += ["AvgPeak(KB)", "MaxPeak(KB)"]
        widths += [12, 12]

    def _row(cols: list[str]) -> str:
        parts = [cols[0].ljust(widths[0])]
        parts += [c.rjust(w) for c, w in zip(cols[1:], widths[1:])]
        return "  " + "  ".join(parts)

    header = _row(headers)
    divider = "  " + "-" * (len(header) - 2)

    ordered = sorted(players, key=lambda n: -tracker.avg_wall_ms(n))
    rows = []
    for name in ordered:
        cols = [
            name,
            str(tracker.call_count(name)),
            f"{tracker.avg_wall_ms(name):.3f}",
            f"{tracker.p95_wall_ms(name):.3f}",
            f"{tracker.max_wall_ms(name):.3f}",
            f"{tracker.avg_cpu_ms(name):.3f}",
            f"{tracker.max_cpu_ms(name):.3f}",
        ]
        if memory_on:
            cols += [f"{tracker.avg_peak_kb(name):.1f}", f"{tracker.max_peak_kb(name):.1f}"]
        rows.append(_row(cols))

    lines = [
        f"\n=== Player Performance — {n_games} games ===\n",
        header,
        divider,
        *rows,
    ]
    return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `just pytest tests/test_perf.py -v`
Expected: all 14 tests pass (9 from Task 1 + 5 new).

- [ ] **Step 5: Run full suite to check for regressions**

Run: `just pytest-all`
Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add game/components/series.py tests/test_perf.py
git commit -m "$(cat <<'EOF'
feat(game): add format_perf() table formatter for PerfTracker

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Engine wiring — `game_orchestrator(perf=...)`

**Files:**

- Modify: `game/components/script.py`
- Modify: `tests/test_main.py`

**Interfaces:**

- Consumes: `PerfTracker.time_call(player_name: str)` from Task 1.
- Produces: `game_orchestrator(..., perf=None)` — new optional kwarg, untyped (matches the existing untyped `stats=None` param already on this function).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_main.py`:

```python
def test_perf_tracker_records_calls_for_each_player():
    """game_orchestrator(perf=tracker) records one call per player per turn taken."""
    from game.components.perf import PerfTracker

    class Caller:
        name = "Caller"

        def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):
            return None  # always call liar — game ends in one round

    class Bidder:
        name = "Bidder"

        def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):
            if prior_bet is None:
                return Bet(1, 2, self.name)
            return Bet(prior_bet.quantity + 1, prior_bet.face, self.name)

    tracker = PerfTracker()
    game_orchestrator([Bidder(), Caller()], bet_history=[], perf=tracker)

    assert tracker.call_count("Bidder") >= 1
    assert tracker.call_count("Caller") >= 1


def test_perf_tracker_records_call_even_when_player_raises():
    """A player that raises still gets its call timed (finally runs before re-raise)."""
    from game.components.perf import PerfTracker

    class Crasher:
        name = "Crasher"

        def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):
            raise RuntimeError("boom")

    class AlwaysBid:
        name = "AlwaysBid"

        def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):
            if prior_bet is None:
                return Bet(1, 2, self.name)
            return Bet(prior_bet.quantity + 1, prior_bet.face, self.name)

    tracker = PerfTracker()
    game_orchestrator([Crasher(), AlwaysBid()], bet_history=[], perf=tracker)

    assert tracker.call_count("Crasher") >= 1


def test_game_orchestrator_runs_without_perf_tracker():
    """perf=None (the default) must not change existing behaviour."""

    class Caller:
        name = "Caller"

        def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):
            return None

    class Bidder:
        name = "Bidder"

        def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):
            if prior_bet is None:
                return Bet(1, 2, self.name)
            return Bet(prior_bet.quantity + 1, prior_bet.face, self.name)

    winner = game_orchestrator([Bidder(), Caller()], bet_history=[])
    assert winner is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `just pytest tests/test_main.py::test_perf_tracker_records_calls_for_each_player -v`
Expected: `TypeError: game_orchestrator() got an unexpected keyword argument 'perf'`

- [ ] **Step 3: Modify `game/components/script.py` — signature**

Change:

```python
def game_orchestrator(
    players: list,
    game_id: int = 1,
    bet_history: list[dict] | None = None,
    outcomes: list[dict] | None = None,
    stats=None,
    tier: str | None = None,
    seed: int | None = None,
):
```

To:

```python
def game_orchestrator(
    players: list,
    game_id: int = 1,
    bet_history: list[dict] | None = None,
    outcomes: list[dict] | None = None,
    stats=None,
    tier: str | None = None,
    seed: int | None = None,
    perf=None,
):
```

- [ ] **Step 4: Modify `game/components/script.py` — wrap both `algo()` call sites**

Change:

```python
            try:
                safe_bet = (
                    Bet(current_bet.quantity, current_bet.face, current_bet.player)
                    if current_bet is not None
                    else None
                )
                if _is_v2[player]:
                    ctx = GameContext(
                        hand=list(hands[player_idx]),
                        prior_bet=safe_bet,
                        total_dice=total_dice,
                        bet_history=bet_history_view,
                        outcomes=outcomes_view,
                        stats=stats,
                        tier=tier,
                        round_players=round_players_order,
                    )
                    action = player.algo(ctx)
                else:
                    kwargs: dict = {}
                    if _wants_stats[player]:
                        kwargs["stats"] = stats
                    if _wants_tier[player]:
                        kwargs["tier"] = tier
                    if _wants_round_players[player]:
                        kwargs["round_players"] = list(round_players_order)
                    action = player.algo(
                        list(hands[player_idx]),
                        safe_bet,
                        total_dice,
                        list(bet_history),
                        list(completed_outcomes),
                        **kwargs,
                    )
            except Exception:
```

To:

```python
            try:
                safe_bet = (
                    Bet(current_bet.quantity, current_bet.face, current_bet.player)
                    if current_bet is not None
                    else None
                )
                if _is_v2[player]:
                    ctx = GameContext(
                        hand=list(hands[player_idx]),
                        prior_bet=safe_bet,
                        total_dice=total_dice,
                        bet_history=bet_history_view,
                        outcomes=outcomes_view,
                        stats=stats,
                        tier=tier,
                        round_players=round_players_order,
                    )
                    if perf is not None:
                        with perf.time_call(player.name):
                            action = player.algo(ctx)
                    else:
                        action = player.algo(ctx)
                else:
                    kwargs: dict = {}
                    if _wants_stats[player]:
                        kwargs["stats"] = stats
                    if _wants_tier[player]:
                        kwargs["tier"] = tier
                    if _wants_round_players[player]:
                        kwargs["round_players"] = list(round_players_order)
                    if perf is not None:
                        with perf.time_call(player.name):
                            action = player.algo(
                                list(hands[player_idx]),
                                safe_bet,
                                total_dice,
                                list(bet_history),
                                list(completed_outcomes),
                                **kwargs,
                            )
                    else:
                        action = player.algo(
                            list(hands[player_idx]),
                            safe_bet,
                            total_dice,
                            list(bet_history),
                            list(completed_outcomes),
                            **kwargs,
                        )
            except Exception:
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `just pytest tests/test_main.py -v -k perf_tracker or test_game_orchestrator_runs_without_perf_tracker`
Expected: all 3 new tests pass.

- [ ] **Step 6: Run full suite to check for regressions**

Run: `just pytest-all`
Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add game/components/script.py tests/test_main.py
git commit -m "$(cat <<'EOF'
feat(game): wire optional PerfTracker into game_orchestrator

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: `run_series(perf=...)` + `SeriesResult.perf`

**Files:**

- Modify: `game/components/series.py`
- Modify: `tests/test_main.py`

**Interfaces:**

- Consumes: `game_orchestrator(..., perf=...)` from Task 3.
- Produces: `run_series(..., perf: PerfTracker | None = None)`, `SeriesResult.perf: PerfTracker | None`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_main.py`:

```python
def test_run_series_perf_tracker_accumulates_across_games():
    """run_series(perf=tracker) records calls across all games, not just one."""
    from game.components.perf import PerfTracker
    from game.components.series import run_series

    class Caller:
        name = "Caller"

        def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):
            return None

    class Bidder:
        name = "Bidder"

        def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):
            if prior_bet is None:
                return Bet(1, 2, self.name)
            return Bet(prior_bet.quantity + 1, prior_bet.face, self.name)

    tracker = PerfTracker()
    result = run_series([Bidder(), Caller()], n_games=3, perf=tracker)

    assert result.perf is tracker
    assert tracker.call_count("Bidder") >= 3
    assert tracker.call_count("Caller") >= 3


def test_run_series_perf_defaults_to_none():
    from game.components.series import run_series

    class Caller:
        name = "Caller"

        def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):
            return None

    class Bidder:
        name = "Bidder"

        def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):
            if prior_bet is None:
                return Bet(1, 2, self.name)
            return Bet(prior_bet.quantity + 1, prior_bet.face, self.name)

    result = run_series([Bidder(), Caller()], n_games=1)
    assert result.perf is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `just pytest tests/test_main.py::test_run_series_perf_tracker_accumulates_across_games -v`
Expected: `TypeError: run_series() got an unexpected keyword argument 'perf'`

- [ ] **Step 3: Modify `game/components/series.py`**

Change:

```python
@dataclass
class SeriesResult:
    wins: dict[str, int]
    stats: GameStats
    outcomes: list[dict] | None = None
    tier: str | None = None


def run_series(
    players: list,
    n_games: int,
    tier: str | None = None,
    capture_outcomes: bool = False,
    on_game_complete: Callable[[int, dict[str, int], GameStats], None] | None = None,
    record_seeds: list[int] | None = None,
    replay_seeds: list[int] | None = None,
) -> SeriesResult:
```

To:

```python
@dataclass
class SeriesResult:
    wins: dict[str, int]
    stats: GameStats
    perf: PerfTracker | None = None
    outcomes: list[dict] | None = None
    tier: str | None = None


def run_series(
    players: list,
    n_games: int,
    tier: str | None = None,
    capture_outcomes: bool = False,
    on_game_complete: Callable[[int, dict[str, int], GameStats], None] | None = None,
    record_seeds: list[int] | None = None,
    replay_seeds: list[int] | None = None,
    perf: PerfTracker | None = None,
) -> SeriesResult:
```

Then change the `game_orchestrator(...)` call inside the loop:

```python
        winner = game_orchestrator(
            players,
            game_id=game_num,
            bet_history=bet_history,
            outcomes=outcomes,
            stats=stats,
            tier=tier,
            seed=_seed,
        )
```

To:

```python
        winner = game_orchestrator(
            players,
            game_id=game_num,
            bet_history=bet_history,
            outcomes=outcomes,
            stats=stats,
            tier=tier,
            seed=_seed,
            perf=perf,
        )
```

And change the return statement:

```python
    return SeriesResult(
        wins=wins,
        stats=stats,
        outcomes=outcomes if capture_outcomes else None,
        tier=tier,
    )
```

To:

```python
    return SeriesResult(
        wins=wins,
        stats=stats,
        perf=perf,
        outcomes=outcomes if capture_outcomes else None,
        tier=tier,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `just pytest tests/test_main.py -v -k run_series_perf`
Expected: both new tests pass.

- [ ] **Step 5: Run full suite to check for regressions**

Run: `just pytest-all`
Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add game/components/series.py tests/test_main.py
git commit -m "$(cat <<'EOF'
feat(game): thread perf tracker through run_series and SeriesResult

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: `season.py` wiring + `--profile-memory` CLI flag

**Files:**

- Modify: `game/simulation/season.py`
- Modify: `tests/test_perf.py`

**Interfaces:**

- Consumes: `PerfTracker` (Task 1), `format_perf` (Task 2), `run_series(..., perf=...)` (Task 4).
- Produces: `run_season(..., profile_memory: bool = False)`; `--profile-memory` CLI flag on `uv run python -m game.simulation.season`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_perf.py`:

```python
def test_run_season_profile_memory_prints_perf_table(tmp_path, capsys):
    from game.simulation.season import run_season

    lb = tmp_path / "lb.yaml"
    lb.write_text(
        "players:\n"
        "  Alice:\n    tier: CH\n    display_name: Alice\n    github_username: ''\n    tier_stats: {}\n"
        "  Bruno:\n    tier: CH\n    display_name: Bruno\n    github_username: ''\n    tier_stats: {}\n"
    )

    run_season(n_games=3, top_n=4, lb_path=str(lb), week_num=1, profile_memory=True)

    output = capsys.readouterr().out
    assert "Player Performance" in output
    assert "Peak" in output


def test_run_season_default_profile_memory_off(tmp_path, capsys):
    from game.simulation.season import run_season

    lb = tmp_path / "lb.yaml"
    lb.write_text(
        "players:\n"
        "  Alice:\n    tier: CH\n    display_name: Alice\n    github_username: ''\n    tier_stats: {}\n"
        "  Bruno:\n    tier: CH\n    display_name: Bruno\n    github_username: ''\n    tier_stats: {}\n"
    )

    run_season(n_games=3, top_n=4, lb_path=str(lb), week_num=1)

    output = capsys.readouterr().out
    assert "Player Performance" in output
    assert "Peak" not in output
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `just pytest tests/test_perf.py::test_run_season_profile_memory_prints_perf_table -v`
Expected: `TypeError: run_season() got an unexpected keyword argument 'profile_memory'`

- [ ] **Step 3: Modify `game/simulation/season.py` — signature and imports**

Change:

```python
def run_season(
    n_games: int,
    top_n: int,
    lb_path: str,
    players_dir: str | None = None,
    dashboard=None,
    replaydb=None,
    week_num: int = 1,
    recording: bool = False,
) -> dict[str, dict[str, int]]:
    """Run one season step in-process. Returns {tier: {player: win_count}}.

    Args:
        n_games: Games per tier/pool.
        top_n: League capacity per PRM/CH tier (TOP_N).
        lb_path: Path to leaderboard.yaml.
        players_dir: Path to players/ directory. Defaults to repo root / players.
        dashboard: Optional TuiAdapter instance for live display.
        replaydb: Optional ReplayDB instance for seed recording/replay.
        week_num: Week number for seed indexing (default 1).
        recording: If True and replaydb is set, record seeds; if False, replay seeds.
    """
    from game.components.leaderboard import (
        apply_season_results,
        get_tier_players,
        settle_relegations,
    )
    from game.components.series import format_results, run_series
    from game.components.utils import apply_display_names, import_player_classes_from_dir
    from game.season.utils import _load_lb, form_pools
```

To:

```python
def run_season(
    n_games: int,
    top_n: int,
    lb_path: str,
    players_dir: str | None = None,
    dashboard=None,
    replaydb=None,
    week_num: int = 1,
    recording: bool = False,
    profile_memory: bool = False,
) -> dict[str, dict[str, int]]:
    """Run one season step in-process. Returns {tier: {player: win_count}}.

    Args:
        n_games: Games per tier/pool.
        top_n: League capacity per PRM/CH tier (TOP_N).
        lb_path: Path to leaderboard.yaml.
        players_dir: Path to players/ directory. Defaults to repo root / players.
        dashboard: Optional TuiAdapter instance for live display.
        replaydb: Optional ReplayDB instance for seed recording/replay.
        week_num: Week number for seed indexing (default 1).
        recording: If True and replaydb is set, record seeds; if False, replay seeds.
        profile_memory: If True, also track tracemalloc peak-allocation bytes per
            algo() call (adds overhead — off by default).
    """
    from game.components.leaderboard import (
        apply_season_results,
        get_tier_players,
        settle_relegations,
    )
    from game.components.perf import PerfTracker
    from game.components.series import format_perf, format_results, run_series
    from game.components.utils import apply_display_names, import_player_classes_from_dir
    from game.season.utils import _load_lb, form_pools

    perf = PerfTracker(profile_memory=profile_memory)
```

- [ ] **Step 4: Modify `game/simulation/season.py` — pass `perf` into both `run_series()` calls**

Change (L1 pool branch):

```python
                result = run_series(
                    pool,
                    n_games,
                    on_game_complete=dashboard.update if dashboard else None,
                    record_seeds=record_seeds,
                    replay_seeds=replay_seeds,
                )
```

To:

```python
                result = run_series(
                    pool,
                    n_games,
                    on_game_complete=dashboard.update if dashboard else None,
                    record_seeds=record_seeds,
                    replay_seeds=replay_seeds,
                    perf=perf,
                )
```

Change (else branch):

```python
            result = run_series(
                players,
                n_games,
                tier=tier,
                on_game_complete=dashboard.update if dashboard else None,
                record_seeds=record_seeds,
                replay_seeds=replay_seeds,
            )
```

To:

```python
            result = run_series(
                players,
                n_games,
                tier=tier,
                on_game_complete=dashboard.update if dashboard else None,
                record_seeds=record_seeds,
                replay_seeds=replay_seeds,
                perf=perf,
            )
```

- [ ] **Step 5: Modify `game/simulation/season.py` — print the perf table before returning**

Change:

```python
    relegations = settle_relegations(
        tier_results, top_n, path=lb_path, tier_stats=tier_series_stats
    )
    if relegations:
        print("[settle] cross-tier relegations:")
        for m in relegations:
            print(f"  {m}")

    return tier_results
```

To:

```python
    relegations = settle_relegations(
        tier_results, top_n, path=lb_path, tier_stats=tier_series_stats
    )
    if relegations:
        print("[settle] cross-tier relegations:")
        for m in relegations:
            print(f"  {m}")

    perf_output = format_perf(perf, n_games)
    if perf_output:
        print(perf_output)

    return tier_results
```

- [ ] **Step 6: Modify `game/simulation/season.py` — CLI flag and threading in `main()`**

Change:

```python
    parser.add_argument(
        "--tui",
        action="store_true",
        default=False,
        help="Launch the Textual TUI dashboard.",
    )
    parser.add_argument("--save-replay", action="store_true", default=False)
```

To:

```python
    parser.add_argument(
        "--tui",
        action="store_true",
        default=False,
        help="Launch the Textual TUI dashboard.",
    )
    parser.add_argument(
        "--profile-memory",
        action="store_true",
        default=False,
        help="Enable tracemalloc-based peak memory profiling per algo() call (adds overhead).",
    )
    parser.add_argument("--save-replay", action="store_true", default=False)
```

Change the TUI-branch call:

```python
            adapter.run(
                lambda: run_season(
                    args.n_games,
                    top_n,
                    lb_path,
                    dashboard=adapter,
                    replaydb=replaydb,
                    week_num=1,
                    recording=recording,
                )
            )
```

To:

```python
            adapter.run(
                lambda: run_season(
                    args.n_games,
                    top_n,
                    lb_path,
                    dashboard=adapter,
                    replaydb=replaydb,
                    week_num=1,
                    recording=recording,
                    profile_memory=args.profile_memory,
                )
            )
```

Change the plain-branch call:

```python
        else:
            run_season(
                args.n_games,
                top_n,
                lb_path,
                replaydb=replaydb,
                week_num=1,
                recording=recording,
            )
```

To:

```python
        else:
            run_season(
                args.n_games,
                top_n,
                lb_path,
                replaydb=replaydb,
                week_num=1,
                recording=recording,
                profile_memory=args.profile_memory,
            )
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `just pytest tests/test_perf.py -v -k run_season`
Expected: both new tests pass.

- [ ] **Step 8: Run full suite to check for regressions**

Run: `just pytest-all`
Expected: all tests pass.

- [ ] **Step 9: Commit**

```bash
git add game/simulation/season.py tests/test_perf.py
git commit -m "$(cat <<'EOF'
feat(game): print PerfTracker table in simulate-season, add --profile-memory

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: `tournament.py` wiring + `--profile-memory` CLI flag

**Files:**

- Modify: `game/simulation/tournament.py`
- Modify: `tests/test_perf.py`

**Interfaces:**

- Consumes: same as Task 5, applied to `run_tournament()`.
- Produces: `run_tournament(..., profile_memory: bool = False)`; `--profile-memory` flag on `uv run python -m game.simulation.tournament`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_perf.py`:

```python
def test_run_tournament_profile_memory_prints_perf_table(tmp_path, capsys):
    from game.simulation.tournament import run_tournament

    lb = tmp_path / "lb.yaml"
    lb.write_text(
        "players:\n"
        "  Alice:\n    tier: CH\n    display_name: Alice\n    github_username: ''\n    tier_stats: {}\n"
        "  Bruno:\n    tier: CH\n    display_name: Bruno\n    github_username: ''\n    tier_stats: {}\n"
    )

    run_tournament(n_games=3, lb_path=str(lb), week_num=1, profile_memory=True)

    output = capsys.readouterr().out
    assert "Player Performance" in output
    assert "Peak" in output
```

- [ ] **Step 2: Run test to verify it fails**

Run: `just pytest tests/test_perf.py::test_run_tournament_profile_memory_prints_perf_table -v`
Expected: `TypeError: run_tournament() got an unexpected keyword argument 'profile_memory'`

- [ ] **Step 3: Modify `game/simulation/tournament.py` — signature, imports, tracker creation**

Change:

```python
def run_tournament(
    n_games: int,
    lb_path: str,
    players_dir: str | None = None,
    dashboard=None,
    replaydb=None,
    week_num: int = 1,
    recording: bool = False,
) -> dict[str, dict[str, int]]:
    """Run a full tournament in-process. Returns {pool_key: {player: win_count}}.

    Zeroes tier_stats, seeds players by prior tier+win%, forms pools,
    runs each pool's games, then assigns placements top-down.

    Args:
        n_games: Games per pool.
        lb_path: Path to leaderboard.yaml.
        players_dir: Path to players/ directory. Defaults to repo root / players.
        dashboard: Optional TuiAdapter instance for live display.
        replaydb: Optional ReplayDB instance for seed recording/replay.
        week_num: Week number for seed indexing (default 1 for tournament).
        recording: If True and replaydb is set, record seeds; if False, replay seeds.
    """
    from game.components.leaderboard import get_tier_players
    from game.components.series import format_results, run_series
    from game.components.utils import apply_display_names, import_player_classes_from_dir
    from game.season.utils import _load_lb, _save_lb, current_quarter, form_pools
```

To:

```python
def run_tournament(
    n_games: int,
    lb_path: str,
    players_dir: str | None = None,
    dashboard=None,
    replaydb=None,
    week_num: int = 1,
    recording: bool = False,
    profile_memory: bool = False,
) -> dict[str, dict[str, int]]:
    """Run a full tournament in-process. Returns {pool_key: {player: win_count}}.

    Zeroes tier_stats, seeds players by prior tier+win%, forms pools,
    runs each pool's games, then assigns placements top-down.

    Args:
        n_games: Games per pool.
        lb_path: Path to leaderboard.yaml.
        players_dir: Path to players/ directory. Defaults to repo root / players.
        dashboard: Optional TuiAdapter instance for live display.
        replaydb: Optional ReplayDB instance for seed recording/replay.
        week_num: Week number for seed indexing (default 1 for tournament).
        recording: If True and replaydb is set, record seeds; if False, replay seeds.
        profile_memory: If True, also track tracemalloc peak-allocation bytes per
            algo() call (adds overhead — off by default).
    """
    from game.components.leaderboard import get_tier_players
    from game.components.perf import PerfTracker
    from game.components.series import format_perf, format_results, run_series
    from game.components.utils import apply_display_names, import_player_classes_from_dir
    from game.season.utils import _load_lb, _save_lb, current_quarter, form_pools

    perf = PerfTracker(profile_memory=profile_memory)
```

- [ ] **Step 4: Modify `game/simulation/tournament.py` — pass `perf` into `run_series()` and print the table**

Change:

```python
        result = run_series(
            pool,
            n_games,
            on_game_complete=dashboard.update if dashboard else None,
            record_seeds=record_seeds,
            replay_seeds=replay_seeds,
        )
```

To:

```python
        result = run_series(
            pool,
            n_games,
            on_game_complete=dashboard.update if dashboard else None,
            record_seeds=record_seeds,
            replay_seeds=replay_seeds,
            perf=perf,
        )
```

Change:

```python
    # Assign placements
    _assign_placements(lb_path, pool_results)
    return pool_results
```

To:

```python
    perf_output = format_perf(perf, n_games)
    if perf_output:
        print(perf_output)

    # Assign placements
    _assign_placements(lb_path, pool_results)
    return pool_results
```

- [ ] **Step 5: Modify `game/simulation/tournament.py` — CLI flag and threading in `main()`**

Change:

```python
    parser.add_argument(
        "--tui",
        action="store_true",
        default=False,
        help="Launch the Textual TUI dashboard.",
    )
    parser.add_argument("--save-replay", action="store_true", default=False)
```

To:

```python
    parser.add_argument(
        "--tui",
        action="store_true",
        default=False,
        help="Launch the Textual TUI dashboard.",
    )
    parser.add_argument(
        "--profile-memory",
        action="store_true",
        default=False,
        help="Enable tracemalloc-based peak memory profiling per algo() call (adds overhead).",
    )
    parser.add_argument("--save-replay", action="store_true", default=False)
```

Change the TUI-branch call:

```python
            adapter.run(
                lambda: run_tournament(
                    args.n_games,
                    lb_path,
                    dashboard=adapter,
                    replaydb=replaydb,
                    week_num=1,
                    recording=recording,
                )
            )
```

To:

```python
            adapter.run(
                lambda: run_tournament(
                    args.n_games,
                    lb_path,
                    dashboard=adapter,
                    replaydb=replaydb,
                    week_num=1,
                    recording=recording,
                    profile_memory=args.profile_memory,
                )
            )
```

Change the plain-branch call:

```python
        else:
            run_tournament(
                args.n_games,
                lb_path,
                replaydb=replaydb,
                week_num=1,
                recording=recording,
            )
```

To:

```python
        else:
            run_tournament(
                args.n_games,
                lb_path,
                replaydb=replaydb,
                week_num=1,
                recording=recording,
                profile_memory=args.profile_memory,
            )
```

- [ ] **Step 6: Run test to verify it passes**

Run: `just pytest tests/test_perf.py::test_run_tournament_profile_memory_prints_perf_table -v`
Expected: PASS.

- [ ] **Step 7: Run full suite to check for regressions**

Run: `just pytest-all`
Expected: all tests pass.

- [ ] **Step 8: Commit**

```bash
git add game/simulation/tournament.py tests/test_perf.py
git commit -m "$(cat <<'EOF'
feat(game): print PerfTracker table in simulate-tournament, add --profile-memory

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: `quarter.py` — thread `--profile-memory` through `run_step()`

**Files:**

- Modify: `game/simulation/quarter.py`
- Modify: `tests/test_simulate_quarter.py`

**Interfaces:**

- Consumes: `run_season(..., profile_memory=...)` (Task 5), `run_tournament(..., profile_memory=...)` (Task 6).
- Produces: `run_step(..., profile_memory: bool = False)`; `--profile-memory` flag on `uv run python -m game.simulation.quarter`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_simulate_quarter.py`:

```python
def test_run_step_passes_profile_memory_to_run_tournament(monkeypatch):
    from game.simulation.quarter import run_step

    calls = []

    def fake_run_tournament(n_games, lb_path, dashboard=None, **kwargs):
        calls.append(kwargs.get("profile_memory"))

    import sys

    fake_mod = type(sys)("game.simulation.tournament")
    fake_mod.run_tournament = fake_run_tournament
    monkeypatch.setitem(sys.modules, "game.simulation.tournament", fake_mod)

    run_step(date(2026, 7, 6), "tournament", n_games=5, lb_path="lb.yaml", profile_memory=True)
    assert calls == [True]


def test_run_step_defaults_profile_memory_to_false(monkeypatch):
    from game.simulation.quarter import run_step

    calls = []

    def fake_run_season(n_games, top_n, lb_path, dashboard=None, **kwargs):
        calls.append(kwargs.get("profile_memory"))

    import sys

    fake_mod = type(sys)("game.simulation.season")
    fake_mod.run_season = fake_run_season
    monkeypatch.setitem(sys.modules, "game.simulation.season", fake_mod)

    run_step(date(2026, 7, 13), "season", n_games=5, lb_path="lb.yaml")
    assert calls == [False]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `just pytest tests/test_simulate_quarter.py::test_run_step_passes_profile_memory_to_run_tournament -v`
Expected: `TypeError: run_step() got an unexpected keyword argument 'profile_memory'`

- [ ] **Step 3: Modify `game/simulation/quarter.py` — `run_step()` signature and both dispatch calls**

Change:

```python
def run_step(
    step_date: date,
    mode: str,
    n_games: int,
    lb_path: str,
    dashboard=None,
    replaydb=None,
    week_num: int = 1,
    recording: bool = False,
) -> str:
    """Run one Monday step in-process. Returns captured stdout text for the report.

    TuiAdapter writes to stderr so it reaches the terminal even while stdout
    is redirected here for report capture.
    """
    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        if mode == "tournament":
            from game.simulation.tournament import run_tournament

            run_tournament(
                n_games=n_games,
                lb_path=lb_path,
                dashboard=dashboard,
                replaydb=replaydb,
                week_num=week_num,
                recording=recording,
            )
        else:
            from game.simulation.season import run_season

            run_season(
                n_games=n_games,
                top_n=int(os.environ.get("TOP_N", "4")),
                lb_path=lb_path,
                dashboard=dashboard,
                replaydb=replaydb,
                week_num=week_num,
                recording=recording,
            )
    output = buf.getvalue()
    print(output, end="")
    return output
```

To:

```python
def run_step(
    step_date: date,
    mode: str,
    n_games: int,
    lb_path: str,
    dashboard=None,
    replaydb=None,
    week_num: int = 1,
    recording: bool = False,
    profile_memory: bool = False,
) -> str:
    """Run one Monday step in-process. Returns captured stdout text for the report.

    TuiAdapter writes to stderr so it reaches the terminal even while stdout
    is redirected here for report capture.
    """
    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        if mode == "tournament":
            from game.simulation.tournament import run_tournament

            run_tournament(
                n_games=n_games,
                lb_path=lb_path,
                dashboard=dashboard,
                replaydb=replaydb,
                week_num=week_num,
                recording=recording,
                profile_memory=profile_memory,
            )
        else:
            from game.simulation.season import run_season

            run_season(
                n_games=n_games,
                top_n=int(os.environ.get("TOP_N", "4")),
                lb_path=lb_path,
                dashboard=dashboard,
                replaydb=replaydb,
                week_num=week_num,
                recording=recording,
                profile_memory=profile_memory,
            )
    output = buf.getvalue()
    print(output, end="")
    return output
```

- [ ] **Step 4: Modify `game/simulation/quarter.py` — CLI flag in `parse_args()`**

Change:

```python
    parser.add_argument(
        "--tui",
        action="store_true",
        default=False,
        help="Launch the Textual TUI dashboard.",
    )
    parser.add_argument(
        "--save-replay",
        action="store_true",
        default=False,
        help="Save seeds and initial state to a .replay file alongside the report.",
    )
```

To:

```python
    parser.add_argument(
        "--tui",
        action="store_true",
        default=False,
        help="Launch the Textual TUI dashboard.",
    )
    parser.add_argument(
        "--profile-memory",
        action="store_true",
        default=False,
        help="Enable tracemalloc-based peak memory profiling per algo() call (adds overhead).",
    )
    parser.add_argument(
        "--save-replay",
        action="store_true",
        default=False,
        help="Save seeds and initial state to a .replay file alongside the report.",
    )
```

- [ ] **Step 5: Modify `game/simulation/quarter.py` — thread the flag through both `run_step()` call sites in `main()`**

Change (inside the `_run_quarter()` closure used by the `--tui` branch):

```python
                    output = run_step(
                        step_date,
                        mode,
                        n_games,
                        lb_path,
                        dashboard=adapter,
                        replaydb=replaydb,
                        week_num=i + 1,
                        recording=recording,
                    )
```

To:

```python
                    output = run_step(
                        step_date,
                        mode,
                        n_games,
                        lb_path,
                        dashboard=adapter,
                        replaydb=replaydb,
                        week_num=i + 1,
                        recording=recording,
                        profile_memory=args.profile_memory,
                    )
```

Change (the plain non-TUI branch):

```python
                output = run_step(
                    step_date,
                    mode,
                    n_games,
                    lb_path,
                    replaydb=replaydb,
                    week_num=i + 1,
                    recording=recording,
                )
```

To:

```python
                output = run_step(
                    step_date,
                    mode,
                    n_games,
                    lb_path,
                    replaydb=replaydb,
                    week_num=i + 1,
                    recording=recording,
                    profile_memory=args.profile_memory,
                )
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `just pytest tests/test_simulate_quarter.py -v -k profile_memory`
Expected: both new tests pass.

- [ ] **Step 7: Run full suite to check for regressions**

Run: `just pytest-all`
Expected: all tests pass.

- [ ] **Step 8: Commit**

```bash
git add game/simulation/quarter.py tests/test_simulate_quarter.py
git commit -m "$(cat <<'EOF'
feat(game): thread --profile-memory through simulate-quarter's weekly steps

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Done

All 7 tasks complete. At this point:

- `just simulate-season`, `just simulate-tournament`, and `just simulate-quarter` all print a "Player Performance" table (wall/CPU time always, memory columns with `--profile-memory`).
- Production CI (`.github/scripts/run_season.py`, `game/__main__.py`) is untouched.
- `leaderboard.yaml` schema is untouched.

Do not push to `origin` or open a PR without checking with the user first — this branch (`feat/player-perf-instrumentation`) lives in a worktree (`.claude/worktrees/player-perf-instrumentation`) precisely so `main` stays clean in the meantime.
