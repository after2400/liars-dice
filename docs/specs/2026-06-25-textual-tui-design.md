# Textual TUI Design

**Date:** 2026-06-25
**Status:** Approved
**Branch:** feat/textual-tui
**Replaces:** `game/dashboard.py` (rich.Live dashboard, Phase 1)

## Problem

The rich.Live dashboard (Phase 1) owns a fixed terminal region and cannot scroll. Any `print()` output outside `live.update()` causes flicker. There is no way to review stats from a completed series once the next one starts. As the simulation grows richer — multiple tournament pools, 13 weekly runs per quarter — the inability to navigate history and see log output alongside stats becomes a real bottleneck for bot tuning.

## Goal

A full Textual TUI that replaces the rich dashboard. A persistent tab per series run (Live + history), drill-down stats for any player in the current series, a cumulative panel that appears when it is meaningful, and a scrollable log panel always visible at the bottom.

---

## Section 1: App Structure and Threading Model

Textual owns the main thread (its async event loop). The simulation is synchronous Python and must run in a background worker thread.

### TuiAdapter

`TuiAdapter` is the sole public interface — it replaces `Dashboard` for all simulation callers. Its API matches the existing pattern:

```python
class TuiAdapter:
    def __init__(self, n_games: int) -> None: ...
    def __enter__(self) -> "TuiAdapter": ...
    def __exit__(self, *args) -> None: ...
    def start_series(self, label: str) -> None: ...
    def update(self, game_num: int, wins: dict[str, int], stats) -> None: ...
    def on_series_complete(self, label: str, result) -> None: ...
```

On `__enter__`, `TuiAdapter` starts a `LiarsDiceApp` instance. The simulation callers pass their callbacks to `TuiAdapter` exactly as they did to `Dashboard`. Internally, `TuiAdapter` routes each call through `app.call_from_thread(app.post_message, ...)` — keeping the simulation thread decoupled from the Textual event loop.

### Worker launch

The simulation runs synchronously in a `threading.Thread` spawned by the `TuiAdapter` on `__enter__`. The Textual app starts in the main thread (blocking until the app exits). When the simulation thread finishes, it posts a `SimulationComplete` message; the app handles this by re-enabling quit and showing a "Simulation complete — press q to exit" notice in the log panel.

### Message types

Four custom Textual `Message` subclasses carry data from the simulation thread to the app:

| Message              | Fields                                            | Trigger                                        |
| -------------------- | ------------------------------------------------- | ---------------------------------------------- |
| `SeriesStarted`      | `label: str`                                      | `start_series()`                               |
| `GameComplete`       | `game_num: int`, `wins: dict`, `stats: GameStats` | `update()`                                     |
| `SeriesComplete`     | `label: str`, `result: SeriesResult`              | `on_series_complete()`                         |
| `SimulationComplete` | _(none)_                                          | simulation thread exits                        |
| `LogLine`            | `text: str`                                       | print() in simulation thread (via `LogStream`) |

---

## Section 2: File Structure

`game/dashboard.py` is deleted. Replaced by:

```
game/tui/
  __init__.py      — exports TuiAdapter (sole public symbol)
  app.py           — LiarsDiceApp(App), message handlers, worker launch
  widgets.py       — StandingsWidget, PlayerStatsPanel, LogPanel
  messages.py      — SeriesStarted, GameComplete, SeriesComplete, SimulationComplete
```

`resolve_player_names()` moves from `game/dashboard.py` into `game/tui/__init__.py` (it is unrelated to rich and still needed for CLI name resolution).

`PlayerAggregate` dataclass moves from `game/dashboard.py` into `game/tui/app.py` (it is internal state of the app's accumulation logic).

---

## Section 3: Screen Layout

```
┌─────────────────────────────────────────────────────────────┐
│  [Live] [Pool 0] [Pool 1] [Week 1] [Week 2] …               │  ← TabbedContent
│ ─────────────────────────────────────────────────────────── │
│  STANDINGS  Pool 1 — Game 412/1000                          │  ← StandingsWidget
│  Oracle         412  41.2%  █████████████░░░░░░░           │    (top, fixed height)
│  EvilStewie     389  38.9%  ████████████░░░░░░░            │
│  NukeLaLoosh    199  19.9%  ██████░░░░░░░░░░░░░            │    ↑↓ to navigate
│                                                             │    Enter to drill in
│ ─────────────────────────────────────────────────────────── │
│  ┌─ Oracle: This Week ──────┐ ┌─ Oracle: Sim Total ──────┐  │  ← ScrollableContainer
│  │  Win Rate  41.2%  ██████ │ │  Win Rate  28.4%  ██████ │  │    PlayerStatsPanel
│  │  …                      │ │  …                        │  │    per drilled player
│  └─────────────────────────┘ └───────────────────────────┘  │    (scrollable)
│  ┌─ EvilStewie: This Week ──┐ ┌─ EvilStewie: Sim Total ──┐  │
│  │  …                      │ │  …                        │  │
│  └─────────────────────────┘ └───────────────────────────┘  │
│ ─────────────────────────────────────────────────────────── │
│  LOG  [v] verbose                              ↑↓ scroll    │  ← LogPanel (docked)
│  [run] Pool 1: Oracle, EvilStewie, NukeLaLoosh              │    always visible
│  [done] Pool 0: Oracle 412 wins                             │    regardless of tab
└─────────────────────────────────────────────────────────────┘
```

**Tab bar** — tabs are added dynamically as series start. The Live tab is always first and always present. History tabs are appended in order: Pool 0, Pool 1, Week 1, Week 2, etc.

**StandingsWidget** — fixed height (number of players + 2 header rows). Shows all players in the current series sorted by wins descending, with win count, win %, and a bar. Cursor-navigable with `↑`/`↓`. Enter drills the highlighted player in below.

**ScrollableContainer** — middle region between standings and log. Holds stacked `PlayerStatsPanel` widgets. Scrolls independently of standings and log. Players can be drilled in without limit; scroll to see them all.

**PlayerStatsPanel** — two columns: left ("This Week") shows live stats for the current series; right ("Sim Total") shows cumulative stats across all completed series plus the live current one. See Section 5 for when the right column is shown.

**LogPanel** — docked to the bottom, fixed height (~8 rows). A Textual `RichLog` widget. Always visible regardless of which tab is active. `v` toggles verbose mode. Scrollable with `↑`/`↓` when focused.

---

## Section 4: History Tabs

When `SeriesComplete` fires, the app takes `copy.deepcopy` of the final `(wins, stats, aggregates)` for that series and attaches it to a new history tab labelled with the series name (e.g., "Pool 0", "Week 1").

History tabs render the same layout as the Live tab but are fully static:

- Standings show the final sorted win counts with no cursor or drill-in interaction (read-only)
- No players are pre-drilled; the tab opens showing standings only
- The right ("Sim Total") panel in a history tab shows totals _as of that series_ — not the running quarter total

History tabs never update after creation. Switching between tabs is `←`/`→` or clicking the tab label.

---

## Section 5: Cumulative Panel Visibility

The right ("Sim Total") column of a `PlayerStatsPanel` is shown only when the player's `_series_baseline.total_games > 0` at the start of the current series. This means:

- **Tournament only** — every player's baseline is zero throughout; right column never appears. Live tab renders each player panel as a single wide column.
- **Single season run** — same; right column never appears.
- **Quarter sim** — after the tournament completes and Week 1 begins, every player who played in the tournament has `baseline.total_games > 0`; right column appears and remains for all subsequent weeks.

When the right column is hidden, the left column expands to fill the full panel width.

---

## Section 6: Log Panel

The simulation's `print()` calls run in the worker thread. On `__enter__` (before the simulation thread starts), `TuiAdapter` replaces `sys.stdout` globally with a `LogStream` object and restores it in `__exit__` (after `app.run()` returns). This is safe because Textual uses Rich's internal `Console` (not `sys.stdout`) for all its own rendering.

```python
class LogStream:
    def write(self, text: str) -> None:
        if text.strip():
            app.call_from_thread(app.post_message, LogLine(text.rstrip()))
    def flush(self) -> None:
        pass
```

`sys.stdout` is restored on `__exit__`. No changes are required in any simulation code — all existing `[run]`, `[done]`, `[skip]`, promotion/relegation lines appear in the log automatically.

**Verbose mode** — toggled with `v`. When on, the `on_game_complete` path additionally emits a `LogLine` per game: `game {n}: {winner} wins (round {rounds})`. This data is already available from `wins` and `stats`; no engine changes required.

---

## Section 7: Keyboard Navigation

| Key       | Action                                           |
| --------- | ------------------------------------------------ |
| `←` / `→` | Switch tabs                                      |
| `↑` / `↓` | Navigate standings rows (when standings focused) |
| `Enter`   | Drill selected player into ScrollableContainer   |
| `Escape`  | Remove bottom-most drilled player panel          |
| `v`       | Toggle verbose log                               |
| `Tab`     | Cycle focus: standings → player panels → log     |
| `q`       | Quit (enabled after SimulationComplete)          |

---

## Section 8: CLI Changes

`--dashboard-players` is removed from all three simulation scripts. The flag to activate the TUI is simply:

```
--tui
```

Usage:

```bash
just simulate-quarter 2026-07-06 500 --tui
just simulate-season 2026-07-13 --tui
just simulate-tournament --tui
```

`resolve_player_names()` is retained in `game/tui/__init__.py` for use by future features that may need class-name-to-display-name resolution.

---

## Section 9: Migration Scope

| File                            | Change                                                                                   |
| ------------------------------- | ---------------------------------------------------------------------------------------- |
| `game/dashboard.py`             | **Deleted**                                                                              |
| `game/tui/__init__.py`          | New — exports `TuiAdapter`, `resolve_player_names`                                       |
| `game/tui/app.py`               | New — `LiarsDiceApp`, `PlayerAggregate`, message handlers                                |
| `game/tui/widgets.py`           | New — `StandingsWidget`, `PlayerStatsPanel`, `LogPanel`                                  |
| `game/tui/messages.py`          | New — `SeriesStarted`, `GameComplete`, `SeriesComplete`, `SimulationComplete`, `LogLine` |
| `game/simulation/season.py`     | `Dashboard` → `TuiAdapter`, `--dashboard-players` → `--tui`                              |
| `game/simulation/tournament.py` | Same                                                                                     |
| `game/simulation/quarter.py`    | Same                                                                                     |
| `pyproject.toml`                | Add `textual` to dependencies                                                            |

Render functions (`_render_left`, `_render_right`, `_render_overview`, `_build_display_aggregate`, `_bar`, `_pct`) are retained verbatim and moved into `game/tui/widgets.py`. They produce plain strings that become the content of Textual `Static` widgets — no changes to the rendering logic itself.

---

## Out of Scope

- Command palette / search
- Mouse click support (beyond what Textual provides by default)
- Pause/resume simulation
- Export/save stats to file from within the TUI
- Parallel pool runs (tracked separately in issue #118)
