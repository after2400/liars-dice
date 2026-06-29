# SQLite In-Memory SimDB Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the manual in-memory accumulation in the TUI (`PlayerAggregate`, `_accumulate`, `_build_display_aggregate`, `_series_baseline`) with a SQLite `:memory:` database so that per-player, per-week, per-tier stats are queryable via SQL.

**Architecture:** A new `SimDB` class in `game/tui/simdb.py` owns a single `sqlite3` `:memory:` connection. After each series completes the TUI inserts one row per player into three tables (`series`, `h2h`, `challenge_by_face`). `query_aggregate(player)` runs SQL aggregations and returns the existing `PlayerAggregate` DTO, so render functions (`_render_right`, `_tier_table_agg`) are unchanged. The live mid-series left panel continues to use `GameStats` directly — SQLite only receives writes at series-complete. Both inserts and reads happen on the Textual event loop (main thread), so thread safety is handled by a `threading.Lock` on the connection as a precaution.

**Tech Stack:** Python `sqlite3` (stdlib, `:memory:` mode), Textual, existing `GameStats` / `SeriesResult` types.

## Global Constraints

- Always use `uv run python` — never bare `python3` or `python`
- Run tests with `just pytest-all` before each commit; all 256+ must pass
- Commit messages must pass commitlint (`type(scope): message`); valid types include `feat`, `fix`, `refactor`; scope `(engine)` is appropriate here
- PR / commit footer: `🤖 Co-Authored with [Claude Code](https://claude.com/claude-code)`
- Python 3.11 compatibility — no `type X = ...` syntax; use `X = ...` for type aliases
- `PlayerAggregate` and `TierStats` remain in `game/tui/widgets.py` as DTOs; `SimDB` imports them from there

---

## File Map

| File                       | Action     | Purpose                                                                                                                                         |
| -------------------------- | ---------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| `game/tui/simdb.py`        | **Create** | `SimDB` class: schema, `insert_series`, `query_aggregate`                                                                                       |
| `tests/test_simdb.py`      | **Create** | Unit tests for all `SimDB` methods                                                                                                              |
| `game/tui/app.py`          | **Modify** | Remove `_aggregates`, `_series_baseline`, `_accumulate`; add `self._db`; add `_current_step_label`; rewire handlers                             |
| `game/tui/widgets.py`      | **Modify** | `PlayerStatsPanel`: remove `baseline` param + `update_baseline`; add `_aggregate` field + `update_aggregate`; remove `_build_display_aggregate` |
| `tests/test_tui_render.py` | **Modify** | Remove two stale `_build_display_aggregate` tests                                                                                               |

---

## Task 1: SimDB — schema and `insert_series`

**Files:**

- Create: `game/tui/simdb.py`
- Create: `tests/test_simdb.py`

**Interfaces:**

- Consumes: `SeriesResult` from `game.components.series` (has `.wins`, `.stats`, `.tier`)
- Consumes: `GameStats` properties: `games_played`, `rounds_played`, `penalty_count`, `die_losses_from_bluff`, `die_losses_from_challenge`, `challenge_success_by_face`, `challenge_count_by_face` — all `dict` or `dict[str, dict]`
- Produces: `SimDB` class with `__init__` and `insert_series(step_label, tier, result)` for Task 2 and Task 3

- [ ] **Step 1: Write failing tests**

```python
# tests/test_simdb.py

def _make_stats(player: str, games: int = 100, wins: int = 40):
    from game.components.stats import GameStats
    s = GameStats()
    s._games_played[player] = games
    s._rounds_played[player] = games * 10
    s._penalty_count[player] = 2
    return s


def test_schema_creates_three_tables():
    from game.tui.simdb import SimDB
    db = SimDB()
    tables = {r[0] for r in db._conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    assert tables == {"series", "h2h", "challenge_by_face"}


def test_insert_series_writes_series_row():
    from game.components.series import SeriesResult
    from game.tui.simdb import SimDB
    stats = _make_stats("Oracle")
    result = SeriesResult(wins={"Oracle": 40, "EvilStewie": 60}, stats=stats, tier="CH")
    db = SimDB()
    db.insert_series("Week 1", "CH", result)
    row = db._conn.execute(
        "SELECT step_label, tier, wins, games, rounds, penalties "
        "FROM series WHERE player='Oracle'"
    ).fetchone()
    assert row == ("Week 1", "CH", 40, 100, 1000, 2)


def test_insert_series_writes_h2h_rows():
    from game.components.series import SeriesResult
    from game.tui.simdb import SimDB
    stats = _make_stats("Oracle")
    stats._die_losses_from_bluff["Oracle"]["EvilStewie"] = 15
    stats._die_losses_from_challenge["Oracle"]["EvilStewie"] = 10
    stats._die_losses_from_bluff["EvilStewie"]["Oracle"] = 8
    result = SeriesResult(
        wins={"Oracle": 40, "EvilStewie": 60}, stats=stats, tier="CH"
    )
    db = SimDB()
    db.insert_series("Week 1", "CH", result)
    row = db._conn.execute(
        "SELECT lost_bluff, lost_challenge, won_bluff, won_challenge "
        "FROM h2h WHERE player='Oracle' AND opponent='EvilStewie'"
    ).fetchone()
    assert row == (15, 10, 8, 0)


def test_insert_series_writes_challenge_by_face_rows():
    from game.components.series import SeriesResult
    from game.tui.simdb import SimDB
    stats = _make_stats("Oracle")
    stats._challenge_success_by_face["Oracle"][6] = 65
    stats._challenge_count_by_face["Oracle"][6] = 100
    result = SeriesResult(wins={"Oracle": 40}, stats=stats, tier="CH")
    db = SimDB()
    db.insert_series("Week 1", "CH", result)
    row = db._conn.execute(
        "SELECT successes, total FROM challenge_by_face WHERE player='Oracle' AND face=6"
    ).fetchone()
    assert row == (65, 100)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
just pytest tests/test_simdb.py -v
```

Expected: `ModuleNotFoundError: No module named 'game.tui.simdb'`

- [ ] **Step 3: Implement `SimDB` with schema and `insert_series`**

```python
# game/tui/simdb.py
from __future__ import annotations

import sqlite3
import threading

from game.components.series import SeriesResult

_SCHEMA = """
CREATE TABLE series (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    step_label  TEXT    NOT NULL,
    tier        TEXT,
    player      TEXT    NOT NULL,
    wins        INTEGER NOT NULL,
    games       INTEGER NOT NULL,
    rounds      INTEGER NOT NULL,
    penalties   INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE h2h (
    series_id       INTEGER NOT NULL,
    player          TEXT    NOT NULL,
    opponent        TEXT    NOT NULL,
    lost_bluff      INTEGER NOT NULL DEFAULT 0,
    lost_challenge  INTEGER NOT NULL DEFAULT 0,
    won_bluff       INTEGER NOT NULL DEFAULT 0,
    won_challenge   INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE challenge_by_face (
    series_id  INTEGER NOT NULL,
    player     TEXT    NOT NULL,
    face       INTEGER NOT NULL,
    successes  INTEGER NOT NULL DEFAULT 0,
    total      INTEGER NOT NULL DEFAULT 0
);
"""


class SimDB:
    """SQLite :memory: store for completed-series stats. Thread-safe via a lock."""

    def __init__(self) -> None:
        self._conn = sqlite3.connect(":memory:", check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock:
            self._conn.executescript(_SCHEMA)

    def insert_series(
        self, step_label: str, tier: str | None, result: SeriesResult
    ) -> None:
        """Insert one row per player from a completed SeriesResult into all tables."""
        stats = result.stats
        with self._lock:
            for player in stats.games_played:
                cur = self._conn.execute(
                    "INSERT INTO series (step_label, tier, player, wins, games, rounds, penalties) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        step_label,
                        tier,
                        player,
                        result.wins.get(player, 0),
                        stats.games_played.get(player, 0),
                        stats.rounds_played.get(player, 0),
                        stats.penalty_count.get(player, 0),
                    ),
                )
                series_id = cur.lastrowid

                bluff_losses = stats.die_losses_from_bluff.get(player, {})
                call_losses = stats.die_losses_from_challenge.get(player, {})
                bluff_src = stats.die_losses_from_bluff
                call_src = stats.die_losses_from_challenge
                opponents = (
                    set(bluff_losses)
                    | set(call_losses)
                    | {opp for opp, v in bluff_src.items() if player in v}
                    | {opp for opp, v in call_src.items() if player in v}
                )
                for opp in opponents:
                    self._conn.execute(
                        "INSERT INTO h2h "
                        "(series_id, player, opponent, lost_bluff, lost_challenge, won_bluff, won_challenge) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (
                            series_id,
                            player,
                            opp,
                            bluff_losses.get(opp, 0),
                            call_losses.get(opp, 0),
                            bluff_src.get(opp, {}).get(player, 0),
                            call_src.get(opp, {}).get(player, 0),
                        ),
                    )

                cs_by_face = stats.challenge_success_by_face.get(player, {})
                cc_by_face = stats.challenge_count_by_face.get(player, {})
                for face in set(cs_by_face) | set(cc_by_face):
                    self._conn.execute(
                        "INSERT INTO challenge_by_face (series_id, player, face, successes, total) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (
                            series_id,
                            player,
                            face,
                            cs_by_face.get(face, 0),
                            cc_by_face.get(face, 0),
                        ),
                    )
            self._conn.commit()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
just pytest tests/test_simdb.py -v
```

Expected: 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add game/tui/simdb.py tests/test_simdb.py
git commit -m "feat(engine): add SimDB with SQLite in-memory schema and insert_series"
```

---

## Task 2: SimDB — `query_aggregate`

**Files:**

- Modify: `game/tui/simdb.py`
- Modify: `tests/test_simdb.py`

**Interfaces:**

- Consumes: `PlayerAggregate`, `TierStats` from `game.tui.widgets`
- Produces: `SimDB.query_aggregate(player: str) -> PlayerAggregate` for Task 3

- [ ] **Step 1: Write failing tests**

Add to `tests/test_simdb.py`:

```python
def test_query_aggregate_empty_returns_zero_aggregate():
    from game.tui.simdb import SimDB
    from game.tui.widgets import PlayerAggregate
    db = SimDB()
    agg = db.query_aggregate("Oracle")
    assert isinstance(agg, PlayerAggregate)
    assert agg.wins == 0
    assert agg.total_games == 0
    assert agg.per_tier == {}


def test_query_aggregate_sums_across_two_series():
    from game.components.series import SeriesResult
    from game.tui.simdb import SimDB
    db = SimDB()
    for n_wins in [30, 40]:
        stats = _make_stats("Oracle", games=100)
        result = SeriesResult(wins={"Oracle": n_wins}, stats=stats, tier="CH")
        db.insert_series("Week 1", "CH", result)
    agg = db.query_aggregate("Oracle")
    assert agg.wins == 70
    assert agg.total_games == 200
    assert agg.rounds_played == 2000
    assert agg.penalties == 4


def test_query_aggregate_tier_breakdown():
    from game.components.series import SeriesResult
    from game.tui.simdb import SimDB
    db = SimDB()
    for tier, wins in [("L1", 50), ("CH", 40)]:
        stats = _make_stats("Oracle", games=100, wins=wins)
        result = SeriesResult(wins={"Oracle": wins}, stats=stats, tier=tier)
        db.insert_series("Week 1", tier, result)
    agg = db.query_aggregate("Oracle")
    assert set(agg.per_tier.keys()) == {"L1", "CH"}
    assert agg.per_tier["L1"].wins == 50
    assert agg.per_tier["CH"].wins == 40
    assert agg.per_tier["L1"].games == 100


def test_query_aggregate_h2h():
    from game.components.series import SeriesResult
    from game.tui.simdb import SimDB
    stats = _make_stats("Oracle")
    stats._die_losses_from_bluff["Oracle"]["EvilStewie"] = 15
    stats._die_losses_from_challenge["Oracle"]["EvilStewie"] = 10
    stats._die_losses_from_bluff["EvilStewie"]["Oracle"] = 8
    stats._die_losses_from_challenge["EvilStewie"]["Oracle"] = 3
    result = SeriesResult(
        wins={"Oracle": 40, "EvilStewie": 60}, stats=stats, tier="CH"
    )
    db = SimDB()
    db.insert_series("Week 1", "CH", result)
    agg = db.query_aggregate("Oracle")
    assert agg.die_losses_from_bluff.get("EvilStewie") == 15
    assert agg.die_losses_from_challenge.get("EvilStewie") == 10
    assert agg.die_wins_from_bluff.get("EvilStewie") == 8
    assert agg.die_wins_from_challenge.get("EvilStewie") == 3


def test_query_aggregate_challenge_by_face():
    from game.components.series import SeriesResult
    from game.tui.simdb import SimDB
    stats = _make_stats("Oracle")
    stats._challenge_success_by_face["Oracle"][6] = 65
    stats._challenge_count_by_face["Oracle"][6] = 100
    stats._challenge_success_by_face["Oracle"][2] = 20
    stats._challenge_count_by_face["Oracle"][2] = 50
    result = SeriesResult(wins={"Oracle": 40}, stats=stats, tier="CH")
    db = SimDB()
    db.insert_series("Week 1", "CH", result)
    agg = db.query_aggregate("Oracle")
    assert agg.challenge_success_by_face.get(6) == 65
    assert agg.challenge_total_by_face.get(6) == 100
    assert agg.challenge_success_by_face.get(2) == 20
    assert agg.challenge_total_by_face.get(2) == 50
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
just pytest tests/test_simdb.py -v
```

Expected: new tests FAIL with `AttributeError: 'SimDB' object has no attribute 'query_aggregate'`

- [ ] **Step 3: Implement `query_aggregate`**

Add to `game/tui/simdb.py` (after the `insert_series` method, inside the class):

```python
    def query_aggregate(self, player: str) -> "PlayerAggregate":
        """Return a PlayerAggregate populated from all completed series for player."""
        from game.tui.widgets import PlayerAggregate, TierStats

        agg = PlayerAggregate()
        with self._lock:
            row = self._conn.execute(
                "SELECT SUM(wins), SUM(games), SUM(rounds), SUM(penalties) "
                "FROM series WHERE player = ?",
                (player,),
            ).fetchone()
            if row and row[0] is not None:
                agg.wins = row[0]
                agg.total_games = row[1]
                agg.rounds_played = row[2]
                agg.penalties = row[3]

            for tier, wins, games, rounds in self._conn.execute(
                "SELECT tier, SUM(wins), SUM(games), SUM(rounds) "
                "FROM series WHERE player = ? AND tier IS NOT NULL GROUP BY tier",
                (player,),
            ):
                agg.per_tier[tier] = TierStats(
                    games=games, wins=wins, rounds_played=rounds
                )

            for opp, lb, lc, wb, wc in self._conn.execute(
                "SELECT opponent, SUM(lost_bluff), SUM(lost_challenge), "
                "SUM(won_bluff), SUM(won_challenge) "
                "FROM h2h WHERE player = ? GROUP BY opponent",
                (player,),
            ):
                if lb:
                    agg.die_losses_from_bluff[opp] = lb
                if lc:
                    agg.die_losses_from_challenge[opp] = lc
                if wb:
                    agg.die_wins_from_bluff[opp] = wb
                if wc:
                    agg.die_wins_from_challenge[opp] = wc

            for face, succs, total in self._conn.execute(
                "SELECT face, SUM(successes), SUM(total) "
                "FROM challenge_by_face WHERE player = ? GROUP BY face",
                (player,),
            ):
                agg.challenge_success_by_face[face] = succs
                agg.challenge_total_by_face[face] = total

        return agg
```

- [ ] **Step 4: Run all tests**

```bash
just pytest-all
```

Expected: all tests PASS (256+)

- [ ] **Step 5: Commit**

```bash
git add game/tui/simdb.py tests/test_simdb.py
git commit -m "feat(engine): add SimDB.query_aggregate returning PlayerAggregate from SQL"
```

---

## Task 3: Wire SimDB into app and widgets; remove old accumulation code

**Files:**

- Modify: `game/tui/app.py`
- Modify: `game/tui/widgets.py`
- Modify: `tests/test_tui_render.py`

**Interfaces:**

- Consumes: `SimDB` from `game.tui.simdb` (Tasks 1 & 2)
- `PlayerStatsPanel.__init__(player, n_games)` — `baseline` param removed
- `PlayerStatsPanel.update_aggregate(agg: PlayerAggregate)` — new method, replaces `update_baseline`

- [ ] **Step 1: Update `PlayerStatsPanel` in `game/tui/widgets.py`**

Replace the `PlayerStatsPanel` class (lines ~432–501) with:

```python
class PlayerStatsPanel(Static):
    """Two-column stats panel for one drilled player. Right column shown once any series completes."""

    can_focus = True

    BINDINGS = [("escape", "close_panel", "Close")]

    DEFAULT_CSS = """
    PlayerStatsPanel {
        height: auto;
        margin-bottom: 1;
    }
    PlayerStatsPanel:focus {
        border: solid $accent;
    }
    """

    def __init__(self, player: str, n_games: int) -> None:
        super().__init__("")
        self.player = player
        self._n_games = n_games
        self._aggregate: PlayerAggregate = PlayerAggregate()
        self._step_tiers: StepTiers = {}
        self._current_wins: dict[str, int] = {}
        self._current_stats = None
        self._game_num = 0
        self.update(self._build_renderable())

    def update_step_data(
        self,
        step_tiers: StepTiers,
        wins: dict[str, int],
        stats,
        game_num: int,
    ) -> None:
        self._step_tiers = step_tiers
        self._current_wins = wins
        self._current_stats = stats
        self._game_num = game_num
        self.update(self._build_renderable())

    def update_aggregate(self, agg: PlayerAggregate) -> None:
        self._aggregate = agg
        self.update(self._build_renderable())

    def action_close_panel(self) -> None:
        from game.tui.messages import DrillInPlayer

        self.post_message(DrillInPlayer(self.player))

    def _build_renderable(self):
        left_title = f"{self.player}: This Week — Game {self._game_num}/{self._n_games}"
        left_body = _render_left(
            self.player,
            self._n_games,
            self._step_tiers,
            self._current_wins,
            self._current_stats,
            self._game_num,
        )

        show_right = self._aggregate.total_games > 0
        if show_right:
            right_title = f"{self.player}: Sim Total — {self._aggregate.total_games:,} games"
            right_body = _render_right(self.player, self._aggregate)
            return Columns(
                [Panel(left_body, title=left_title), Panel(right_body, title=right_title)]
            )
        return Panel(left_body, title=left_title)
```

Also remove `_build_display_aggregate` (the entire function at lines ~250–329).

- [ ] **Step 2: Update `game/tui/app.py`**

**2a. Update imports** — remove `copy`, add `SimDB`:

```python
# Remove:
import copy

# Add (with other game.tui imports):
from game.tui.simdb import SimDB
```

**2b. Update `__init__`** — remove `_aggregates`, `_series_baseline`; add `_db`, `_current_step_label`:

```python
def __init__(self, n_games: int, ready_event: threading.Event) -> None:
    super().__init__()
    self._n_games = n_games
    self._ready_event = ready_event
    self._db: SimDB = SimDB()
    self._current_wins: dict[str, int] = {}
    self._current_stats = None
    self._current_game = 0
    self._current_label = ""
    self._current_tier: str | None = None
    self._current_step_label: str = ""
    self._current_step_tier_results: dict[str, tuple] = {}
    self._sim_done = False
    self._drilled: list[str] = []
    self._history_tab_count = 0
    self._step_count = 0
    self._current_step_inner_id: str | None = None
```

**2c. Update `on_step_started`** — add `_current_step_label`:

```python
def on_step_started(self, message: StepStarted) -> None:
    self._step_count += 1
    self._current_step_label = message.label
    self._current_step_tier_results = {}
    inner_id = f"step-tabs-{self._step_count}"
    self._current_step_inner_id = inner_id
    outer_id = f"step-{self._step_count}"
    pane = TabPane(message.label, TabbedContent(id=inner_id), id=outer_id)
    self.query_one("#tabs", TabbedContent).add_pane(pane)
```

**2d. Update `on_game_complete`** — remove the baseline-snapshot block and `panel.update_baseline` call:

```python
def on_game_complete(self, message: GameComplete) -> None:
    self._current_game = message.game_num
    self._current_wins = message.wins
    self._current_stats = message.stats

    standings = self.query_one(StandingsWidget)
    standings.update_standings(
        message.wins,
        message.stats,
        message.game_num,
        self._n_games,
        self._current_label,
    )

    step_tiers = self._build_step_tiers(message.wins, message.stats, message.game_num)
    for panel in self.query(PlayerStatsPanel):
        if panel.player not in message.stats.games_played:
            continue
        panel.update_step_data(step_tiers, message.wins, message.stats, message.game_num)

    log = self.query_one(LogPanel)
    if log.verbose:
        winner = max(message.wins, key=lambda p: message.wins.get(p, 0), default="?")
        log.write_line(
            f"[dim]game {message.game_num}: {winner} leads "
            f"({message.wins.get(winner, 0)} wins)[/dim]"
        )
```

**2e. Update `on_series_complete`** — replace `_accumulate` call with `_db.insert_series`; refresh right panels:

```python
def on_series_complete(self, message: SeriesComplete) -> None:
    tier = message.result.tier
    if tier:
        self._current_step_tier_results[tier] = (
            message.result.wins,
            message.result.stats,
            self._n_games,
        )
    self._db.insert_series(self._current_step_label, tier, message.result)
    self._add_history_tab(message.label, message.result)
    for panel in self.query(PlayerStatsPanel):
        panel.update_aggregate(self._db.query_aggregate(panel.player))
```

**2f. Update `on_drill_in_player`** — remove baseline, use `_db.query_aggregate`:

```python
def on_drill_in_player(self, message: DrillInPlayer) -> None:
    if message.player in self._drilled:
        self._drilled.remove(message.player)
        for panel in self.query(PlayerStatsPanel):
            if panel.player == message.player:
                panel.remove()
                return
        return
    self._drilled.append(message.player)
    step_tiers = self._build_step_tiers(
        self._current_wins, self._current_stats, self._current_game
    )
    panel = PlayerStatsPanel(
        player=message.player,
        n_games=self._n_games,
    )
    panel.update_aggregate(self._db.query_aggregate(message.player))
    panel.update_step_data(
        step_tiers, self._current_wins, self._current_stats, self._current_game
    )
    container = self.query_one("#player-panels", ScrollableContainer)
    container.mount(panel)
```

**2g. Remove `_accumulate` method entirely** — delete the entire `_accumulate` method (lines ~257–305 in current app.py).

Also remove the now-unused import of `TierStats` from `game.tui.widgets` in app.py's import block:

```python
# Remove TierStats from this import:
from game.tui.widgets import (
    LogPanel,
    PlayerAggregate,
    PlayerStatsPanel,
    StandingsWidget,
    TierStats,   # <-- remove this line
)
```

- [ ] **Step 3: Remove stale tests from `tests/test_tui_render.py`**

Delete the two `_build_display_aggregate` tests (they test a function that no longer exists):

```python
# Delete these two test functions entirely:
def test_build_display_aggregate_no_step_tiers(): ...
def test_build_display_aggregate_merges_step_tiers(): ...
```

- [ ] **Step 4: Run all tests**

```bash
just pytest-all
```

Expected: all tests PASS. Count may be slightly lower (2 tests removed) but all remaining must pass.

- [ ] **Step 5: Commit**

```bash
git add game/tui/app.py game/tui/widgets.py tests/test_tui_render.py
git commit -m "refactor(engine): replace in-memory accumulation with SimDB queries

Remove PlayerAggregate manual accumulation (_accumulate, _series_baseline,
_build_display_aggregate). SimDB.query_aggregate now populates the Sim Total
panel via SQL aggregation over completed series rows."
```
