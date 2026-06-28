# Simulation Replay Design

**Date:** 2026-06-27
**Status:** Approved

## Goal

Allow a simulation run to be saved and replayed with one or more tweaked player algorithms, using identical initial conditions and per-game RNG seeds so results are directly comparable. Primary use case: tuning a single bot against a fixed field.

## Scope

Applies to all three simulation entry points: `simulate-quarter`, `simulate-tournament`, `simulate-season`. A single shared data model covers all three.

---

## Architecture

Four layers of change, each independent:

1. **Engine** — seed injection in `game_orchestrator` and `run_series`
2. **ReplayDB** — SQLite file persistence layer (`game/simulation/replaydb.py`)
3. **Simulation callers** — thread `ReplayDB` through season/tournament/quarter
4. **CLI** — `--save-replay` / `--replay` / `--save-leaderboard` flags + Justfile passthrough

---

## Section 1: Data Model

The replay file is a SQLite database with extension `.replay`, co-located with the `.md` report. When `--output sim-2026-Q3.md` is specified (explicitly or by default), the replay file is `sim-2026-Q3.replay`.

### `meta` table

Key/value store. Keys:

| Key                  | Type | Description                                                                       |
| -------------------- | ---- | --------------------------------------------------------------------------------- |
| `mode`               | str  | `"quarter"`, `"tournament"`, or `"season"`                                        |
| `step_date`          | str  | ISO date — tournament start (quarter) or the single step date (tournament/season) |
| `quarter`            | str  | e.g. `"2026-Q3"` (quarter mode only; empty string otherwise)                      |
| `n_games`            | str  | Integer serialised as string                                                      |
| `top_n`              | str  | Integer serialised as string                                                      |
| `lb_snapshot`        | str  | Full `leaderboard.yaml` contents as JSON, captured before any mutation            |
| `created_at`         | str  | ISO datetime of the original run                                                  |
| `original_standings` | str  | JSON blob of per-player final stats from the original run (used for diff report)  |

### `game_seed` table

One row per game:

| Column       | Type    | Description                                                     |
| ------------ | ------- | --------------------------------------------------------------- |
| `week_num`   | INTEGER | 1-based week within the quarter (always 1 for single-step runs) |
| `tier`       | TEXT    | `"PRM"`, `"CH"`, `"L1"`, or `NULL` for tournament pools         |
| `series_idx` | INTEGER | 0-based pool/series index within a week+tier                    |
| `game_num`   | INTEGER | 1-based game number within the series                           |
| `seed`       | INTEGER | 64-bit unsigned seed passed to `random.Random()`                |

Pool assignments are derived deterministically from the lb snapshot via the existing seeding algorithm, so they do not need separate storage.

---

## Section 2: Engine Changes

### `game_orchestrator` (`game/components/script.py`)

Add one optional parameter:

```python
def game_orchestrator(
    players: list,
    game_id: int = 1,
    bet_history: list[dict] | None = None,
    outcomes: list[dict] | None = None,
    stats=None,
    tier: str | None = None,
    seed: int | None = None,       # NEW
):
```

Behaviour: if `seed` is provided, use `random.Random(seed)` instead of `random.Random(secrets.randbits(64))`. The generated seed is no longer accessible to the caller — see `run_series` for capture.

### `run_series` (`game/components/series.py`)

Add two optional parameters:

```python
def run_series(
    players: list,
    n_games: int,
    tier: str | None = None,
    capture_outcomes: bool = False,
    on_game_complete: Callable[[int, dict[str, int], GameStats], None] | None = None,
    record_seeds: list[int] | None = None,   # NEW
    replay_seeds: list[int] | None = None,   # NEW
):
```

Behaviour:

- **`record_seeds`**: before each game, generate a seed via `secrets.randbits(64)`, append it to this list, then pass it to `game_orchestrator`. When `None`, behaviour is unchanged.
- **`replay_seeds`**: consume seeds from this list in order (one per game) instead of generating new ones. Length must equal `n_games`; a mismatch raises `ValueError`.
- `record_seeds` and `replay_seeds` are mutually exclusive; passing both raises `ValueError`.

No changes to `SeriesResult`, `GameStats`, or the player API.

---

## Section 3: ReplayDB

New module: `game/simulation/replaydb.py`

```python
class ReplayDB:
    @classmethod
    def create(cls, path: str | Path) -> "ReplayDB": ...
    @classmethod
    def load(cls, path: str | Path) -> "ReplayDB": ...

    def save_meta(
        self,
        mode: str,
        step_date: date,
        quarter: str,
        n_games: int,
        top_n: int,
        lb_snapshot: dict,
    ) -> None: ...

    def save_standings(self, standings: dict) -> None: ...  # writes original_standings to meta after run

    def save_seed(
        self, week_num: int, tier: str | None, series_idx: int, game_num: int, seed: int
    ) -> None: ...

    def get_meta(self) -> dict[str, str]: ...

    def get_seeds(self, week_num: int, tier: str | None, series_idx: int) -> list[int]: ...

    def close(self) -> None: ...
```

`create` opens a new file (overwrites if exists) and initialises the schema. `load` opens read-only. Both return a `ReplayDB` instance. The class is not a context manager — callers call `close()` explicitly (quarter/tournament/season `main()` functions do this in a `finally` block).

The simulation callers (season, tournament, quarter `run_*` functions) receive a `replaydb: ReplayDB | None = None` parameter. When present:

- Record mode: call `save_meta` once at the start (before any games run), `save_seed` for every game, and `save_standings` once at the end after final standings are computed.
- Replay mode: call `get_seeds` per series to obtain `replay_seeds` before calling `run_series`.

---

## Section 4: CLI

### Flags added to all three entry points

| Flag                 | Type    | Description                                                                                              |
| -------------------- | ------- | -------------------------------------------------------------------------------------------------------- |
| `--save-replay`      | boolean | Derive replay path from output stem and save.                                                            |
| `--replay <path>`    | path    | Load replay file; use its lb snapshot and seeds.                                                         |
| `--save-leaderboard` | boolean | When replaying, write resulting leaderboard to `leaderboard.yaml`. Default: false (replay is read-only). |

`--save-replay` and `--replay` are mutually exclusive.

### Path derivation

Output `.md` path is already determined by `--output` or the default `sim-YYYY-QN.md`. The replay path replaces `.md` with `.replay`:

```
sim-2026-Q3.md   →   sim-2026-Q3.replay
```

For single-step sims where no `.md` is written by default, the replay path is derived from the step date: `sim-2026-07-06.replay`.

### Example invocations

```bash
# Record a quarter sim
just simulate-quarter --tui --save-replay

# Replay after editing players/oracle.py
just simulate-quarter --replay sim-2026-Q3.replay --tui

# Replay and persist resulting leaderboard
just simulate-quarter --replay sim-2026-Q3.replay --save-leaderboard

# Single tournament
just simulate-tournament --save-replay
just simulate-tournament --replay sim-2026-07-06.replay

# Single season step
just simulate-season 2026-07-13 --save-replay
just simulate-season 2026-07-13 --replay sim-2026-07-13.replay
```

The existing `*ARGS` passthrough in `.Justfile` recipes means no new recipe variants are needed.

### Replay startup behaviour

When `--replay` is active:

- The lb snapshot from the file is used as the starting state; `leaderboard.yaml` is not read.
- Tournament-Monday validation is skipped (the replay file's `step_date` is used directly).
- A banner is printed before the simulation starts: `[replay] sim-2026-Q3.replay — <mode>, <n_games> games/run`
- This banner flows through `LogStream` and appears in the TUI log panel.

---

## Section 5: TUI behaviour during replay

No changes to the TUI. A replay run produces the identical message sequence (`StepStarted`, `SeriesStarted`, `GameComplete`, `SeriesComplete`, `SimulationComplete`) as a live run. The `TuiAdapter` receives no changes. The replay banner (Section 4) appears in the log panel as a side effect of stdout capture.

---

## Section 6: Markdown diff report (stretch goal)

When `--replay` is active, a diff report `sim-2026-Q3-diff.md` is generated automatically alongside the replay's `.md` report, provided `original_standings` is present in the replay file's meta.

Contents:

- Per-player, per-tier win% delta (replay minus original)
- Total wins delta
- Promotion/relegation changes (if final tier assignments differ)

Original stats are sourced from the `original_standings` JSON blob in `meta` — no separate file needed. If the blob is absent (replay file predates this feature), the diff report is silently skipped.

---

## Out of scope (phase 2)

- Side-by-side TUI comparison view (original vs replay simultaneously)
- Scrubbing / interactive playback control
- Replay of individual games in isolation
