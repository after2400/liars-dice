# Live Tuning Dashboard Design

**Date:** 2026-06-25
**Status:** Approved

## Problem

The current bot-tuning loop is essentially blind. The only signal available is relative win % aggregated across a full quarter simulation. To improve a parameter, you run an entire quarter, compare win percentages, guess at causality, and repeat. There is also no visibility into what's happening during a run — progress checks require scanning log files or season summaries manually.

## Goal

A real-time terminal dashboard that shows live diagnostic stats for one or more watched bots during any simulation run. Stats should answer the specific questions a bot designer needs to tune parameters: not just _that_ a bot is losing, but _why_ and _to whom_.

---

## Section 1: Data Layer

### New `GameStats` counters

All new counters are O(N²) in player count and **do not grow with game count**. Memory impact is negligible (~5–10 KB for a 5-player series).

#### Updated in `update_outcome()`

**Die-loss cause, per opponent:**

- `die_losses_from_bluff: dict[str, dict[str, int]]` — `[loser][challenger]` when `bet_held == False`
- `die_losses_from_challenge: dict[str, dict[str, int]]` — `[loser][bidder]` when `bet_held == True`

**Per-face call accuracy:**

- `challenge_success_by_face: dict[str, dict[int, int]]` — incremented when `challenger == player` and `bet_held == False`
- `challenge_count_by_face: dict[str, dict[int, int]]` — incremented when `challenger == player`

**Rounds survived:**

- `rounds_played: dict[str, int]` — incremented for every player present in `hands` each round
- `games_played: dict[str, int]` — incremented in `start_game()`

#### New method: `record_penalty(player_name)`

Called from `game_orchestrator` on the three penalty paths (exception, invalid bid, liar-with-no-bet). These currently set `loser` but never call `update_outcome`, making those die losses invisible.

- `penalty_count: dict[str, int]`

#### Derived (no new counters needed)

- **Dice won from opponent X:** `die_losses_from_bluff[X][me] + die_losses_from_challenge[X][me]` — reads from the opponent's perspective using the same counters
- **H2H net:** won − lost, computed at render time

### `SeriesResult` dataclass

Replaces the current `dict[str, int]` return value of `run_series`:

```python
@dataclass
class SeriesResult:
    wins: dict[str, int]
    stats: GameStats
    outcomes: list[dict] | None = None  # only populated if capture_outcomes=True
```

`outcomes` defaults to `None` — the dashboard never needs it, keeping the dashboard path free of the ~14 MB memory cost a 1000-game outcomes list would carry.

---

## Section 2: Callback Hook

### `run_series` signature

```python
def run_series(
    players: list,
    n_games: int,
    tier: str | None = None,
    capture_outcomes: bool = False,
    on_game_complete: Callable[[int, dict[str, int], GameStats], None] | None = None,
) -> SeriesResult:
```

**`on_game_complete(game_num, wins, stats)`** fires after each game, after `stats` is fully updated. The callback runs synchronously in the game thread — no threading, no torn reads, no missed games.

Inside the game loop, one new line after recording the winner:

```python
wins[winner.name] += 1
if on_game_complete is not None:
    on_game_complete(game_num, wins, stats)
```

**Return type change:** all callers currently unpack `wins = run_series(...)`. Mechanical update required:

```python
# before
wins = run_series(players, n_games, tier=tier)

# after
result = run_series(players, n_games, tier=tier)
wins = result.wins
```

Files to update: `run_season.py`, `reset_season.py`, simulation scripts, any tests that call `run_series` directly.

---

## Section 3: Dashboard Module

**Location:** `game/dashboard.py` — single module, separate from `game/components/` since it is UI, not engine.

**Dependency:** `rich` — add to `pyproject.toml` if not already present.

### Layout

Two panels per watched player, side by side. Players stack vertically. Terminal height is respected.

```
┌─ Oracle: This Week ──── Game 247/1000 ─┐ ┌─ Oracle: Sim Total ─── 1,247 games ─┐
│ Win Rate   31.2%  ████████░░░░░░░░░░░ │ │ Win Rate   28.4%  ███████░░░░░░░░░░ │
│ Avg Rounds 12.4 / game  Penalties  3  │ │ Avg Rounds 11.8 / game  Penalties 14 │
│                                        │ │                                      │
│ Die Losses  847 total                  │ │ Die Losses  4,832 total              │
│  Bad bluff   412  48.6%  ████████░░░  │ │  Bad bluff  2,201  45.5%  ███████░░ │
│  Bad call    435  51.4%  █████████░░  │ │  Bad call   2,631  54.5%  ████████░ │
│                                        │ │                                      │
│ Head-to-Head  Lost         Won    Net  │ │ Head-to-Head  Lost         Won   Net │
│               Bluff / Call Bluff / Call│ │               Bluff / Call Bluff /.. │
│  EvilStewie    80 /  44    52 /  37-35 │ │  EvilStewie  412 / 231   287 / 198-… │
│  Alice         55 /  43    72 /  40+14 │ │  Alice       311 / 198   402 / 211+… │
│  Bruno         48 /  39    89 /  45+47 │ │  Bruno       287 / 156   498 / 231+… │
│                                        │ │                                      │
│ Call Accuracy  64.2% overall           │ │ Call Accuracy  61.8% overall         │
│ 1:71% 2:58% 3:62% 4:67% 5:55% 6:70%  │ │ 1:68% 2:55% 3:60% 4:65% 5:53% 6:68% │
└────────────────────────────────────────┘ └──────────────────────────────────────┘
┌─ EvilStewie: This Week ── Game 247/1000┐ ┌─ EvilStewie: Sim Total ─ 1,247 games┐
│ ...                                    │ │ ...                                  │
└────────────────────────────────────────┘ └──────────────────────────────────────┘
```

- **Left panel:** live stats for the current `run_series` call. Updated every game via `on_game_complete`.
- **Right panel:** cumulative stats aggregated across all series in the sim. Updated once per series via `on_series_complete`.
- **Rendering:** `rich.Live` wrapping `rich.Columns` of `rich.Panel` objects. `refresh_per_second=4` — Rich buffers `update()` calls and repaints at the refresh rate, keeping the display smooth without slowing the sim.
- **On exit:** `rich.Live` leaves the final render in the terminal so stats remain readable after the run completes.

### `Dashboard` class API

```python
class Dashboard:
    def __init__(self, watched: list[str], n_games: int): ...
    def __enter__(self) -> "Dashboard": ...
    def __exit__(self, *args) -> None: ...
    def update(self, game_num: int, wins: dict[str, int], stats: GameStats) -> None: ...
    def on_series_complete(self, label: str, result: SeriesResult) -> None: ...
```

### Clipping and CPU optimization

Panel height is ~18 rows (fixed constant, conservative). Visible player count is computed once at `__init__` using `console.height`:

```python
max_visible = max(1, self._console.height // PANEL_HEIGHT)
self._visible = watched[:max_visible]
self._clipped = watched[max_visible:]
self._aggregates = {p: PlayerAggregate() for p in self._visible}
```

`update()` and `on_series_complete()` skip clipped players entirely — no aggregate accumulation, no rendering work. On `__enter__`, if any players are clipped, a one-time warning is printed above the live area:

```
Dashboard: terminal too small to show Bruno, Alice — increase height or watch fewer players
```

### `PlayerAggregate` dataclass

Maintains running totals across series for the right panel:

```python
@dataclass
class PlayerAggregate:
    total_games: int = 0
    wins: int = 0
    die_losses_from_bluff: dict[str, int] = field(default_factory=dict)   # [opponent] caught me
    die_losses_from_challenge: dict[str, int] = field(default_factory=dict)  # [opponent] I challenged wrong
    die_wins_from_bluff: dict[str, int] = field(default_factory=dict)     # [opponent] I caught them
    die_wins_from_challenge: dict[str, int] = field(default_factory=dict) # [opponent] they challenged wrong
    rounds_played: int = 0
    penalties: int = 0
    challenge_successes: int = 0
    challenge_total: int = 0
    challenge_success_by_face: dict[int, int] = field(default_factory=dict)
    challenge_total_by_face: dict[int, int] = field(default_factory=dict)
```

`on_series_complete` reads both the watched player's losses and the inverse (wins) from `result.stats`, since `GameStats` tracks all players — not just watched ones.

---

## Section 4: CLI Integration

### Argument

All three simulation scripts gain:

```
--dashboard-players Oracle,EvilStewie,"Peter Beter"
```

Parsed as a comma-split, whitespace-stripped list of player names.

### Wiring in simulation scripts

```python
if args.dashboard_players:
    watched = [n.strip() for n in args.dashboard_players.split(",")]
    dashboard = Dashboard(watched=watched, n_games=n_games)
else:
    dashboard = None

with (dashboard or nullcontext()):
    for label, players in series_runs:
        result = run_series(
            players, n_games,
            on_game_complete=dashboard.update if dashboard else None,
        )
        if dashboard:
            dashboard.on_series_complete(label, result)
```

### Justfile

Sim recipes updated to use `*ARGS` passthrough:

```makefile
simulate-quarter *ARGS:
    uv run python -m game.simulation.quarter {{ARGS}}

simulate-season *ARGS:
    DRY_RUN=true uv run python -m game.simulation.season {{ARGS}}

simulate-tournament *ARGS:
    DRY_RUN=true uv run python -m game.simulation.tournament {{ARGS}}
```

Usage:

```bash
just simulate-quarter 2026-07-06 500 --dashboard-players Oracle,EvilStewie
just simulate-season 2026-07-13 --dashboard-players Oracle
```

---

## Out of Scope (Phase 2)

**Series history tabs** — a Textual-based interactive TUI with navigable tabs per series run (Pool 1, Pool 2, Week 1, …). Deferred pending Phase 1 validation. Would replace `rich.Live` with a `textual.App` and require a more substantial architecture shift.

---

## Files Affected

| File                            | Change                                                                   |
| ------------------------------- | ------------------------------------------------------------------------ |
| `game/components/stats.py`      | New counters + `record_penalty()` method                                 |
| `game/components/series.py`     | `SeriesResult` dataclass + `on_game_complete` param + return type change |
| `game/components/script.py`     | Call `record_penalty()` on penalty paths                                 |
| `game/dashboard.py`             | New — `Dashboard`, `PlayerAggregate`                                     |
| `run_season.py`                 | Update `run_series` call to unpack `SeriesResult`                        |
| `reset_season.py`               | Same                                                                     |
| `game/simulation/quarter.py`    | Add `--dashboard-players` arg, wire dashboard                            |
| `game/simulation/season.py`     | Same                                                                     |
| `game/simulation/tournament.py` | Same                                                                     |
| `justfile`                      | Update sim recipes to `*ARGS` passthrough                                |
| `pyproject.toml`                | Add `rich` if not present                                                |
| `tests/`                        | Update any tests calling `run_series` directly                           |
