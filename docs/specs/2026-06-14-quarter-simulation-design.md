# Quarter Simulation — Design Spec

**Date:** 2026-06-14
**Status:** Approved

## Problem

Running a full quarter manually requires coordinating ~13 subprocess invocations with the right `TODAY` and `DRY_RUN` env vars in the right order. There's no way to preview what a quarter will look like without doing it for real. Developers working on player bots have no ergonomic way to stress-test their bot across a full quarter.

## Solution

A Python script at `game/simulation/quarter.py` that simulates an entire quarter end-to-end: tournament Monday first, then each subsequent regular Monday, until the next tournament boundary. All runs use `DRY_RUN=true` so no GitHub API calls are made. The script prints output as it goes and writes a plain-Markdown report at the end.

## File Changes

```
game/
  season/
    __init__.py          (new, empty)
    utils.py             (moved from .github/scripts/season_utils.py — no logic changes)
  simulation/
    __init__.py          (new, empty)
    quarter.py           (new)

.github/scripts/
  reset_season.py        (import update: from game.season.utils import ...)
  run_season.py          (import update: from game.season.utils import ...)
```

### Why move season_utils?

`season_utils.py` contains game-domain logic (quarter boundaries, tournament Monday detection, leaderboard I/O). It was originally placed in `.github/scripts/` for CI convenience, but the simulation script makes it clear this logic isn't exclusively CI. Moving it into the `game` package makes it a proper importable module and keeps `.github/scripts/` as pure CI glue that calls into `game/`.

## Architecture

```
quarter.py
├── parse_args()
│     --start YYYY-MM-DD   (default: next_tournament_monday())
│     --output PATH         (default: sim-YYYY-QN.md)
│     --n-games N           (default: N_GAMES env var or 1000)
│
├── compute_mondays(start: date) -> list[tuple[date, str]]
│     Returns [(date, "tournament"|"season"), ...]
│     From start up to (not including) the next tournament Monday.
│
├── run_step(date: date, mode: str, n_games: int) -> str
│     Invokes reset_season.py (tournament) or run_season.py (season) via subprocess.
│     Env: TODAY=YYYY-MM-DD, DRY_RUN=true, N_GAMES=n_games, plus full os.environ passthrough.
│     Streams stdout to console in real-time. Returns captured stdout for the report.
│
├── write_report(steps: list[dict], lb_path: str, output_file: Path) -> None
│     Writes plain Markdown report (see Report Format below).
│
└── main()
      parse_args → compute_mondays → run_step per Monday → write_report
```

## CLI

```bash
# simulate next upcoming quarter (auto-detected)
uv run python -m game.simulation.quarter

# target a specific quarter by its tournament Monday
uv run python -m game.simulation.quarter --start 2026-07-07

# custom report output file
uv run python -m game.simulation.quarter --output reports/q3-2026.md

# fewer games for faster local testing
uv run python -m game.simulation.quarter --n-games 50
```

`DRY_RUN=true` is always set internally — it is not a flag and cannot be overridden. This ensures running the simulation can never trigger GitHub API calls.

## Report Format

Default output filename: `sim-YYYY-QN.md` (e.g. `sim-2026-Q3.md`).

```markdown
# Quarter Simulation: 2026-Q3

**Start:** 2026-07-07 | **Mondays:** 13 | **Games/run:** 1000

## 2026-07-07 — Tournament

[stdout from reset_season.py]

## 2026-07-14 — Week 1

[stdout from run_season.py]

## 2026-07-21 — Week 2

[stdout from run_season.py]

...

---

## Final Standings

### Premier

| Player | Win % in PRM | Wins | Win % Total | Total Wins | Games |
| ------ | ------------ | ---- | ----------- | ---------- | ----- |

...

### Championship

...

### League One

...

_Inactive: ..._
```

Plain Markdown throughout — no `<details>` tags — so the report renders correctly in any viewer.

## Quarter Boundary Logic

A "tournament Monday" is the first Monday of January, April, July, or October (`is_tournament_monday()` in `game/season/utils.py`). The simulation runs from the given start date through the last Monday before the next tournament Monday.

Example — Q3 2026 (July 7 start):

- Tournament: 2026-07-07
- Regular season: 2026-07-14, 07-21, 07-28, 08-04, 08-11, 08-18, 08-25, 09-01, 09-08, 09-15, 09-22, 09-29
- Stops before: 2026-10-06 (Q4 tournament Monday)
- Total: 13 Mondays

## Tests

- `test_compute_mondays`: verify correct Monday sequence and mode labels for a known quarter
- `test_compute_mondays_custom_start`: verify `--start` with a non-default date
- `test_run_step_dry_run`: verify subprocess is called with `DRY_RUN=true` and correct `TODAY`
- `test_write_report`: verify report contains expected headers and Final Standings section

Tests live in `tests/test_simulate_quarter.py`.
