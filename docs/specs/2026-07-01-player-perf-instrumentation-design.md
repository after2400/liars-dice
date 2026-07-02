# Player Performance Instrumentation Design

**Date:** 2026-07-01
**Status:** Approved

## Goal

Instrument the game engine to measure per-player wall-clock time, CPU time, and (optionally) peak memory during `algo()` calls, so player authors can see how expensive their bot is. This is Phase 1 of a two-phase effort:

- **Phase 1 (this spec):** ephemeral instrumentation, surfaced only in local simulation reports (`simulate-season`, `simulate-quarter`, `simulate-tournament`). No production CI wiring, no `leaderboard.yaml` schema changes.
- **Phase 2 (future, not designed here):** persist a rolling CPU-time figure into `leaderboard.yaml` and surface it as a column in the season summary / README standings / tracking-issue posts. Deferred until Phase 1 data shows what's actually worth tracking long-term.

## Scope

Applies to the three in-process simulation entry points (`game/simulation/season.py`, `tournament.py`, `quarter.py`), which all funnel through `game/components/series.run_series()` → `game/components/script.game_orchestrator()`. The production weekly path (`.github/scripts/run_season.py`) does **not** call `run_series()` directly — it shells out per-tier to `game/__main__.py` via `subprocess`. Since `game/__main__.py` will not be changed to request tracking, this work has zero effect on the live Monday CI run.

---

## Architecture

### New file: `game/components/perf.py`

`PerfTracker` — engine-internal instrumentation object. It is never passed into a player's `algo()` (unlike `GameStats`/`GameContext`), so no change to the AST import allowlist in `game/validate.py` is needed.

```python
class PerfTracker:
    def __init__(self, profile_memory: bool = False) -> None: ...
    def time_call(self, player_name: str) -> ContextManager: ...

    # aggregate accessors (computed on read, from stored per-call samples):
    call_count(player_name) -> int
    avg_wall_ms(player_name) -> float
    p95_wall_ms(player_name) -> float
    max_wall_ms(player_name) -> float
    avg_cpu_ms(player_name) -> float
    max_cpu_ms(player_name) -> float
    avg_peak_kb(player_name) -> float | None   # None unless profile_memory
    max_peak_kb(player_name) -> float | None
```

`time_call(player_name)` is a context manager wrapping one `algo()` invocation:

- **Wall time:** `time.perf_counter()` before/after. Always recorded — negligible overhead (a counter read).
- **CPU time:** `time.thread_time()` before/after. Always recorded. Chosen over `time.process_time()` because `process_time()` sums CPU across the whole process, which would be polluted by the Textual TUI's background render thread when `--tui` is active; `thread_time()` isolates the main thread running the game loop. Supported on Linux, macOS, and Windows — covers both local dev and GitHub Actions CI, no fallback needed.
- **Peak memory (opt-in):** only when `profile_memory=True`. `PerfTracker.__init__` calls `tracemalloc.start()` if not already tracing (idempotent — a second `start()` while already tracing is a no-op per stdlib docs). Each call does `tracemalloc.reset_peak()` on enter, then snapshots `tracemalloc.get_traced_memory()[0]` (current, which now equals the reset peak) as a baseline — `reset_peak()` resets the watermark to the _current_ traced total, not zero, so without this step every call's reading would include whatever memory was already alive in the process (accumulated `GameStats`/replay state, etc.), not just its own allocation. On exit, the recorded sample is `get_traced_memory()[1] - baseline`. This measures Python-level allocation peaks per call; it's an approximation (doesn't capture C-extension memory) but is precise enough for spotting a bot that's unusually allocation-heavy.

Per-player samples are stored as plain lists of floats/ints; aggregates (avg/p95/max) are computed lazily when the report is built — this runs once per simulation step, so O(n log n) sorting for p95 is trivial even at 1000 games.

### `format_perf(tracker: PerfTracker, n_games: int) -> str`

Text table in the same style as the existing `format_results()` bar chart, sorted by avg wall time descending (slowest bot first, since that's what you'd want to investigate). Columns: `Player | Calls | Total Wall (s) | Total CPU (s) | Avg Wall (ms) | P95 Wall (ms) | Max Wall (ms) | Avg CPU (ms) | Max CPU (ms)`, plus `Avg Peak (KB) | Max Peak (KB)` when memory profiling was on.

### Engine changes

- `game_orchestrator()` (`game/components/script.py`) gains `perf: PerfTracker | None = None`. Both existing `player.algo(...)` call sites (v2 `ctx`-style and legacy positional) get wrapped:
  ```python
  if perf is not None:
      with perf.time_call(player.name):
          action = player.algo(...)
  else:
      action = player.algo(...)
  ```
  This sits inside the existing `try/except Exception` block, so a player that raises still has its partial time recorded (the context manager's `__exit__` always runs before the exception propagates) — useful, since a slow call that then crashes is exactly the kind of thing this is meant to surface.
- `run_series()` (`game/components/series.py`) gains `perf: PerfTracker | None = None`, forwarded to `game_orchestrator` on every game, and returned on a new `SeriesResult.perf` field.
- `game/__main__.py` is **unchanged** — it calls `run_series()` without `perf=`, so its output (parsed by production `run_season.py`) is untouched.

### Simulation caller changes

- `game/simulation/season.py::run_season()` creates **one `PerfTracker` per season step**, shared across every `run_series()` call within that step (all tiers, all L1 pools). Sharing one tracker avoids needing a pool-merge helper like `_merge_h2h_stats` — samples just accumulate per player name across pools naturally. Prints `format_perf(tracker, n_games)` right after each existing `print(format_results(...))`.
- `game/simulation/tournament.py::run_tournament()` gets the identical treatment (one tracker per tournament run).
- Both gain a `profile_memory: bool = False` parameter.
- CLI: both `season.py` and `tournament.py` gain a `--profile-memory` flag (argparse, matching the existing `--tui`/`--save-replay` style — a per-invocation dev toggle, not an env var like `DRY_RUN`/`N_GAMES`).
- `game/simulation/quarter.py` adds the same `--profile-memory` flag and threads it through `run_step()` into whichever of `run_season()`/`run_tournament()` it calls. No changes to `write_report()` — the printed perf table is captured via the existing `redirect_stdout` + `_format_output` pipeline, so it shows up automatically in each week's section of `sim-YYYY-QN.md`, exactly like the win-rate bar chart does today.

---

## Data flow

```
game_orchestrator(perf=tracker)
  └─ wraps each player.algo() call in tracker.time_call(name)
run_series(perf=tracker)
  └─ passes tracker through every game; returns SeriesResult.perf
run_season()/run_tournament()
  └─ creates tracker once per step, reuses across tiers/pools
  └─ prints format_perf(tracker, n_games)
quarter.py / season.py / tournament.py CLI
  └─ --profile-memory flag controls tracker.profile_memory
  └─ printed table captured into sim-*.md report via existing stdout capture
```

---

## Testing

- `tests/test_perf.py` (new): unit tests for `PerfTracker` — recording a call updates wall/CPU aggregates correctly; `profile_memory=False` leaves peak-memory accessors returning `None`; `profile_memory=True` records non-zero peak bytes for an allocation-heavy dummy call; `format_perf()` output contains expected columns and sorts slowest-first.
- `tests/test_main.py`: extend with a case verifying `game_orchestrator(..., perf=tracker)` records exactly one call per player per turn, and that a call recorded time even when the player's `algo()` raises (penalty path).
- Run `just pytest-all` before committing (engine-level change, per project convention).

## Out of scope (Phase 1)

- Any change to `leaderboard.yaml`, README standings, or the GitHub tracking-issue summary.
- Any change to `.github/scripts/run_season.py` or `game/__main__.py`.
- Enforcement (rejecting or penalizing slow/memory-heavy players) — Phase 1 is observability only.
