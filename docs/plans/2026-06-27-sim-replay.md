# Simulation Replay Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow a simulation run to be saved (seeds + initial state) and replayed with tweaked player algorithms under identical conditions.

**Architecture:** A new `ReplayDB` class wraps a SQLite file storing per-game RNG seeds and the leaderboard snapshot captured at run start. `game_orchestrator` and `run_series` gain optional seed injection params; all three simulation entry points (tournament, season, quarter) gain `--save-replay` / `--replay` / `--save-leaderboard` CLI flags.

**Tech Stack:** Python stdlib `sqlite3`, `json`, `tempfile`, `secrets`; existing `yaml`; no new dependencies.

## Global Constraints

- Always use `uv run python` — never bare `python` or `python3`
- Run tests with `just pytest <path>` or `just pytest-all`
- Commit with `git commit -m "..."` using valid commitlint types/scopes from `.commitlintrc.mjs`; valid scopes include `engine`, `game`, `scripts`, `tests`
- No changes to the player API (`algo` signature)
- `--save-replay` and `--replay` are mutually exclusive; passing both is a CLI error
- `--save-leaderboard` is only valid alongside `--replay`
- In replay mode, `leaderboard.yaml` is never read or written (unless `--save-leaderboard` is passed)
- The spec lives at `docs/specs/2026-06-27-sim-replay-design.md`

---

### Task 1: ReplayDB module

**Files:**

- Create: `game/simulation/replaydb.py`
- Create: `tests/test_replaydb.py`

**Interfaces:**

- Produces:
  - `ReplayDB.create(path: str | Path) -> ReplayDB`
  - `ReplayDB.load(path: str | Path) -> ReplayDB`
  - `db.save_meta(mode, step_date, quarter, n_games, top_n, lb_snapshot) -> None`
  - `db.save_standings(standings: dict) -> None`
  - `db.save_seed(week_num, tier, series_idx, game_num, seed) -> None`
  - `db.get_meta() -> dict[str, str]`
  - `db.get_seeds(week_num, tier, series_idx) -> list[int]`
  - `db.close() -> None`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_replaydb.py
from datetime import date


def test_create_initialises_schema(tmp_path):
    from game.simulation.replaydb import ReplayDB

    db = ReplayDB.create(tmp_path / "run.replay")
    tables = {
        r[0]
        for r in db._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    }
    db.close()
    assert tables == {"meta", "game_seed"}


def test_save_and_get_meta(tmp_path):
    from game.simulation.replaydb import ReplayDB

    db = ReplayDB.create(tmp_path / "run.replay")
    db.save_meta(
        mode="quarter",
        step_date=date(2026, 7, 6),
        quarter="2026-Q3",
        n_games=100,
        top_n=4,
        lb_snapshot={"players": {"Alice": {"tier": "PRM"}}},
    )
    meta = db.get_meta()
    db.close()
    assert meta["mode"] == "quarter"
    assert meta["quarter"] == "2026-Q3"
    assert meta["n_games"] == "100"
    assert meta["top_n"] == "4"
    assert "Alice" in meta["lb_snapshot"]
    assert "created_at" in meta


def test_save_standings_adds_key(tmp_path):
    from game.simulation.replaydb import ReplayDB

    db = ReplayDB.create(tmp_path / "run.replay")
    db.save_meta("tournament", date(2026, 7, 6), "", 50, 4, {})
    db.save_standings({"Oracle": {"tier": "PRM", "tier_stats": {}}})
    meta = db.get_meta()
    db.close()
    assert "Oracle" in meta["original_standings"]


def test_save_and_get_seeds_ordered(tmp_path):
    from game.simulation.replaydb import ReplayDB

    db = ReplayDB.create(tmp_path / "run.replay")
    for game_num, seed in enumerate([111, 222, 333], 1):
        db.save_seed(week_num=1, tier="PRM", series_idx=0, game_num=game_num, seed=seed)
    seeds = db.get_seeds(week_num=1, tier="PRM", series_idx=0)
    db.close()
    assert seeds == [111, 222, 333]


def test_get_seeds_returns_empty_for_missing(tmp_path):
    from game.simulation.replaydb import ReplayDB

    db = ReplayDB.create(tmp_path / "run.replay")
    seeds = db.get_seeds(week_num=99, tier=None, series_idx=0)
    db.close()
    assert seeds == []


def test_seeds_tier_none_stored_correctly(tmp_path):
    from game.simulation.replaydb import ReplayDB

    db = ReplayDB.create(tmp_path / "run.replay")
    db.save_seed(1, None, 0, 1, 999)
    seeds = db.get_seeds(1, None, 0)
    db.close()
    assert seeds == [999]


def test_create_overwrites_existing_file(tmp_path):
    from game.simulation.replaydb import ReplayDB

    path = tmp_path / "run.replay"
    db = ReplayDB.create(path)
    db.save_seed(1, "PRM", 0, 1, 42)
    db.close()
    db2 = ReplayDB.create(path)
    seeds = db2.get_seeds(1, "PRM", 0)
    db2.close()
    assert seeds == []


def test_load_reads_existing_file(tmp_path):
    from game.simulation.replaydb import ReplayDB

    path = tmp_path / "run.replay"
    db = ReplayDB.create(path)
    db.save_seed(1, "CH", 0, 1, 77)
    db.close()

    db2 = ReplayDB.load(path)
    seeds = db2.get_seeds(1, "CH", 0)
    db2.close()
    assert seeds == [77]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
just pytest tests/test_replaydb.py
```

Expected: `ModuleNotFoundError: No module named 'game.simulation.replaydb'`

- [ ] **Step 3: Implement `game/simulation/replaydb.py`**

```python
from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime
from pathlib import Path

_SCHEMA = """
CREATE TABLE meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE game_seed (
    week_num    INTEGER NOT NULL,
    tier        TEXT,
    series_idx  INTEGER NOT NULL,
    game_num    INTEGER NOT NULL,
    seed        INTEGER NOT NULL
);
"""


class ReplayDB:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    @classmethod
    def create(cls, path: str | Path) -> "ReplayDB":
        path = Path(path)
        if path.exists():
            path.unlink()
        conn = sqlite3.connect(str(path))
        conn.executescript(_SCHEMA)
        conn.commit()
        return cls(conn)

    @classmethod
    def load(cls, path: str | Path) -> "ReplayDB":
        conn = sqlite3.connect(str(path))
        return cls(conn)

    def save_meta(
        self,
        mode: str,
        step_date: date,
        quarter: str,
        n_games: int,
        top_n: int,
        lb_snapshot: dict,
    ) -> None:
        entries = [
            ("mode", mode),
            ("step_date", step_date.isoformat()),
            ("quarter", quarter),
            ("n_games", str(n_games)),
            ("top_n", str(top_n)),
            ("lb_snapshot", json.dumps(lb_snapshot)),
            ("created_at", datetime.now().isoformat()),
        ]
        self._conn.executemany(
            "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", entries
        )
        self._conn.commit()

    def save_standings(self, standings: dict) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
            ("original_standings", json.dumps(standings)),
        )
        self._conn.commit()

    def save_seed(
        self,
        week_num: int,
        tier: str | None,
        series_idx: int,
        game_num: int,
        seed: int,
    ) -> None:
        self._conn.execute(
            "INSERT INTO game_seed (week_num, tier, series_idx, game_num, seed) "
            "VALUES (?, ?, ?, ?, ?)",
            (week_num, tier, series_idx, game_num, seed),
        )
        self._conn.commit()

    def get_meta(self) -> dict[str, str]:
        return dict(self._conn.execute("SELECT key, value FROM meta").fetchall())

    def get_seeds(self, week_num: int, tier: str | None, series_idx: int) -> list[int]:
        return [
            row[0]
            for row in self._conn.execute(
                "SELECT seed FROM game_seed "
                "WHERE week_num=? AND tier IS ? AND series_idx=? "
                "ORDER BY game_num",
                (week_num, tier, series_idx),
            ).fetchall()
        ]

    def close(self) -> None:
        self._conn.close()
```

- [ ] **Step 4: Run tests — all must pass**

```bash
just pytest tests/test_replaydb.py
```

Expected: 8 tests pass.

- [ ] **Step 5: Commit**

```bash
git add game/simulation/replaydb.py tests/test_replaydb.py
git commit -m "feat(game): add ReplayDB SQLite persistence for simulation seeds"
```

---

### Task 2: Engine seed injection

**Files:**

- Modify: `game/components/script.py` (line 15 — `game_orchestrator` signature; line 40 — rng init)
- Modify: `game/components/series.py` (add `import secrets`; `run_series` signature and loop body)
- Create: `tests/test_replay_engine.py`

**Interfaces:**

- Consumes: nothing from earlier tasks
- Produces:
  - `game_orchestrator(..., seed: int | None = None)` — uses provided seed instead of generating one
  - `run_series(..., record_seeds: list[int] | None = None, replay_seeds: list[int] | None = None)` — captures or injects seeds

- [ ] **Step 1: Write failing tests**

```python
# tests/test_replay_engine.py
import pytest
from game.components.bets import Bet


class _Bidder:
    """Minimal player: bids 1×1 on first turn, calls liar thereafter."""

    def __init__(self, name: str) -> None:
        self.name = name

    def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):
        if prior_bet is None:
            return Bet(1, 1)
        return None


def _two_players():
    return [_Bidder("A"), _Bidder("B")]


def test_game_orchestrator_with_seed_is_deterministic():
    from game.components.script import game_orchestrator

    players = _two_players()
    winner1 = game_orchestrator(players, seed=12345)
    winner2 = game_orchestrator(players, seed=12345)
    assert type(winner1).__name__ == type(winner2).__name__


def test_game_orchestrator_different_seeds_differ():
    """Different seeds should occasionally produce different winners (probabilistic)."""
    from game.components.script import game_orchestrator

    players = _two_players()
    results = {type(game_orchestrator(players, seed=s)).__name__ for s in range(50)}
    assert len(results) == 2  # both players win at least once across 50 seeds


def test_run_series_record_seeds_captures_one_per_game():
    from game.components.series import run_series

    seeds: list[int] = []
    run_series(_two_players(), n_games=5, record_seeds=seeds)
    assert len(seeds) == 5
    assert all(isinstance(s, int) for s in seeds)


def test_run_series_replay_seeds_deterministic():
    from game.components.series import run_series

    players = _two_players()
    seeds: list[int] = []
    result_a = run_series(players, n_games=10, record_seeds=seeds)

    result_b = run_series(players, n_games=10, replay_seeds=seeds)
    assert result_b.wins == result_a.wins


def test_run_series_mutual_exclusion_raises():
    from game.components.series import run_series

    with pytest.raises(ValueError, match="mutually exclusive"):
        run_series(_two_players(), n_games=2, record_seeds=[], replay_seeds=[1, 2])


def test_run_series_replay_seeds_length_mismatch_raises():
    from game.components.series import run_series

    with pytest.raises(ValueError, match="length"):
        run_series(_two_players(), n_games=3, replay_seeds=[1, 2])


def test_run_series_no_seed_args_unchanged():
    """Baseline: no seed args still runs without error."""
    from game.components.series import run_series

    result = run_series(_two_players(), n_games=3)
    assert sum(result.wins.values()) == 3
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
just pytest tests/test_replay_engine.py
```

Expected: failures on `seed` param and `record_seeds`/`replay_seeds`.

- [ ] **Step 3: Modify `game/components/script.py`**

Change the function signature (line 15) — add `seed: int | None = None`:

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

Change line 40 — use provided seed:

```python
    rng = random.Random(seed if seed is not None else secrets.randbits(64))
```

- [ ] **Step 4: Modify `game/components/series.py`**

Add `import secrets` after the existing imports (line 3 area):

```python
import logging
import secrets
from collections.abc import Callable
from dataclasses import dataclass
```

Update `run_series` signature — add the two new params:

```python
def run_series(
    players: list,
    n_games: int,
    tier: str | None = None,
    capture_outcomes: bool = False,
    on_game_complete: Callable[[int, dict[str, int], GameStats], None] | None = None,
    record_seeds: list[int] | None = None,
    replay_seeds: list[int] | None = None,
) -> SeriesResult:
    if record_seeds is not None and replay_seeds is not None:
        raise ValueError("record_seeds and replay_seeds are mutually exclusive")
    if replay_seeds is not None and len(replay_seeds) != n_games:
        raise ValueError(
            f"replay_seeds length {len(replay_seeds)} != n_games {n_games}"
        )
```

Inside the `for game_num in range(1, n_games + 1):` loop, before the `game_orchestrator` call, add seed selection:

```python
        if replay_seeds is not None:
            _seed: int | None = replay_seeds[game_num - 1]
        elif record_seeds is not None:
            _seed = secrets.randbits(64)
            record_seeds.append(_seed)
        else:
            _seed = None
```

Add `seed=_seed` to the `game_orchestrator` call:

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

- [ ] **Step 5: Run all tests**

```bash
just pytest-all
```

Expected: all existing tests plus the 7 new ones pass.

- [ ] **Step 6: Commit**

```bash
git add game/components/script.py game/components/series.py tests/test_replay_engine.py
git commit -m "feat(engine): add seed injection to game_orchestrator and run_series"
```

---

### Task 3: Wire ReplayDB into tournament.py

**Files:**

- Modify: `game/simulation/tournament.py`
- Create: `tests/test_replay_tournament.py`

**Interfaces:**

- Consumes: `ReplayDB` from Task 1; `run_series(record_seeds=, replay_seeds=)` from Task 2
- Produces:
  - `run_tournament(..., replaydb=None, week_num=1, recording=False)`
  - `main()` gains `--save-replay`, `--replay <path>`, `--save-leaderboard` flags

- [ ] **Step 1: Write failing tests**

```python
# tests/test_replay_tournament.py
from datetime import date
from unittest.mock import MagicMock, patch


def _make_replaydb(tmp_path):
    from game.simulation.replaydb import ReplayDB

    db = ReplayDB.create(tmp_path / "t.replay")
    db.save_meta("tournament", date(2026, 7, 6), "", 10, 4, {})
    return db


def test_run_tournament_records_seeds(tmp_path, monkeypatch):
    """When recording=True, seeds are saved to replaydb."""
    from game.simulation.replaydb import ReplayDB
    from game.simulation.tournament import run_tournament

    db = _make_replaydb(tmp_path)

    saved: list[tuple] = []
    original_save = db.save_seed
    db.save_seed = lambda *a: saved.append(a) or original_save(*a)

    lb = tmp_path / "lb.yaml"
    lb.write_text(
        "players:\n"
        "  Alice:\n    tier: PRM\n    display_name: Alice\n    github_username: ''\n    tier_stats: {}\n"
        "  Bob:\n    tier: PRM\n    display_name: Bob\n    github_username: ''\n    tier_stats: {}\n"
        "tournament_state:\n  quarter: 2026-Q3\n"
    )
    monkeypatch.setenv("LEADERBOARD_PATH", str(lb))

    run_tournament(n_games=5, lb_path=str(lb), replaydb=db, week_num=1, recording=True)
    db.close()

    assert len(saved) == 5
    assert all(row[0] == 1 for row in saved)  # week_num=1
    assert all(row[1] is None for row in saved)  # tier=None for tournament pools
    assert all(row[3] in range(1, 6) for row in saved)  # game_num 1-5


def test_run_tournament_replay_uses_stored_seeds(tmp_path, monkeypatch):
    """Replaying with stored seeds produces identical wins."""
    from game.simulation.replaydb import ReplayDB
    from game.simulation.tournament import run_tournament

    lb = tmp_path / "lb.yaml"
    lb.write_text(
        "players:\n"
        "  Alice:\n    tier: PRM\n    display_name: Alice\n    github_username: ''\n    tier_stats: {}\n"
        "  Bob:\n    tier: PRM\n    display_name: Bob\n    github_username: ''\n    tier_stats: {}\n"
        "tournament_state:\n  quarter: 2026-Q3\n"
    )

    # Record
    replay_path = tmp_path / "t.replay"
    db_record = ReplayDB.create(replay_path)
    db_record.save_meta("tournament", date(2026, 7, 6), "", 20, 4, {})
    run_tournament(n_games=20, lb_path=str(lb), replaydb=db_record, week_num=1, recording=True)
    db_record.save_standings({})
    db_record.close()

    # Restore lb (tournament zeroed tier_stats)
    lb.write_text(
        "players:\n"
        "  Alice:\n    tier: PRM\n    display_name: Alice\n    github_username: ''\n    tier_stats: {}\n"
        "  Bob:\n    tier: PRM\n    display_name: Bob\n    github_username: ''\n    tier_stats: {}\n"
        "tournament_state:\n  quarter: 2026-Q3\n"
    )

    # Replay
    db_replay = ReplayDB.load(replay_path)
    result_replay = run_tournament(n_games=20, lb_path=str(lb), replaydb=db_replay, week_num=1, recording=False)
    db_replay.close()

    # Both runs must produce the same pool results
    # (wins are stored in pool_results inside tournament, and returned)
    assert result_replay is not None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
just pytest tests/test_replay_tournament.py
```

Expected: `TypeError` — `run_tournament()` doesn't accept `replaydb` yet.

- [ ] **Step 3: Update `run_tournament` signature in `game/simulation/tournament.py`**

Change the function signature (line 18):

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
```

Inside the pool loop (around line 84), replace the existing `run_series` call with seed-aware version:

```python
    for i, pool_names in enumerate(pools):
        key = f"pool_{i}"
        pool = [players_by_name[n] for n in pool_names if n in players_by_name]
        if len(pool) < 2:
            print(f"[skip] {key}: {len(pool)} player(s) — need ≥ 2.")
            continue
        print(f"[run] {key}: {pool_names}")
        if dashboard:
            dashboard.start_series(key.replace("_", " ").title())

        record_seeds: list[int] | None = [] if (replaydb is not None and recording) else None
        replay_seeds: list[int] | None = (
            replaydb.get_seeds(week_num, None, i)
            if (replaydb is not None and not recording)
            else None
        )

        result = run_series(
            pool,
            n_games,
            on_game_complete=dashboard.update if dashboard else None,
            record_seeds=record_seeds,
            replay_seeds=replay_seeds,
        )

        if record_seeds is not None and replaydb is not None:
            for gn, seed in enumerate(record_seeds, 1):
                replaydb.save_seed(week_num, None, i, gn, seed)

        if dashboard:
            dashboard.on_series_complete(key, result)
        pool_results[key] = result.wins
        display_wins = {display_map.get(k, k): v for k, v in result.wins.items()}
        print(format_results(display_wins, n_games))
        print(f"[done] {key}: {display_wins}")
```

- [ ] **Step 4: Update `main()` in `game/simulation/tournament.py`**

Add imports at top of file (after existing imports):

```python
import sys
from datetime import date
```

Add new args to `parse_args` section inside `main()` (after existing `--tui` arg):

```python
    parser.add_argument("--save-replay", action="store_true", default=False)
    parser.add_argument("--replay", type=Path, default=None)
    parser.add_argument("--save-leaderboard", action="store_true", default=False)
```

Add validation and replay setup after `args = parser.parse_args()`:

```python
    if args.save_replay and args.replay:
        print("[error] --save-replay and --replay are mutually exclusive", file=sys.stderr)
        sys.exit(1)
    if args.save_leaderboard and not args.replay:
        print("[error] --save-leaderboard requires --replay", file=sys.stderr)
        sys.exit(1)

    if args.date:
        os.environ["TODAY"] = args.date

    lb_path = os.environ.get("LEADERBOARD_PATH", "leaderboard.yaml")
    step_date = date.fromisoformat(args.date) if args.date else date.today()

    from game.simulation.replaydb import ReplayDB

    replaydb = None
    recording = False
    temp_lb_path: str | None = None

    if args.save_replay:
        from game.season.utils import _load_lb

        replay_path = Path(f"sim-{step_date}.replay")
        replaydb = ReplayDB.create(replay_path)
        recording = True
        replaydb.save_meta(
            mode="tournament",
            step_date=step_date,
            quarter="",
            n_games=args.n_games,
            top_n=int(os.environ.get("TOP_N", "4")),
            lb_snapshot=_load_lb(lb_path),
        )
    elif args.replay:
        import json
        import tempfile

        import yaml as _yaml

        replaydb = ReplayDB.load(args.replay)
        meta = replaydb.get_meta()
        lb_data = json.loads(meta["lb_snapshot"])
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
        _yaml.safe_dump(lb_data, tmp)
        tmp.close()
        temp_lb_path = tmp.name
        lb_path = temp_lb_path
        args.n_games = int(meta["n_games"])
        print(f"[replay] {args.replay} — tournament, {args.n_games} games/run")
```

Replace the existing `if args.tui: ... else: run_tournament(...)` block:

```python
    try:
        if args.tui:
            from game.components.utils import apply_display_names, import_player_classes_from_dir
            from game.season.utils import _load_lb
            from game.tui import TuiAdapter

            _all = import_player_classes_from_dir(str(_REPO_ROOT / "players"))
            apply_display_names(_all, _load_lb(lb_path).get("players", {}))
            display_names = {type(p).__name__: p.name for p in _all}
            adapter = TuiAdapter(n_games=args.n_games, display_names=display_names)
            adapter.run(
                lambda: run_tournament(
                    args.n_games, lb_path, dashboard=adapter,
                    replaydb=replaydb, week_num=1, recording=recording,
                )
            )
        else:
            run_tournament(
                args.n_games, lb_path,
                replaydb=replaydb, week_num=1, recording=recording,
            )

        if args.save_replay and replaydb:
            from game.season.utils import _load_lb

            replaydb.save_standings(_load_lb(lb_path).get("players", {}))
            replaydb.close()
            print(f"[done] Replay saved to sim-{step_date}.replay")

        if args.replay and replaydb:
            if args.save_leaderboard:
                import shutil

                real_lb = os.environ.get("LEADERBOARD_PATH", "leaderboard.yaml")
                shutil.copy(lb_path, real_lb)
                print("[done] Leaderboard updated from replay.")
            replaydb.close()

    finally:
        if temp_lb_path:
            os.unlink(temp_lb_path)
```

- [ ] **Step 5: Run tests**

```bash
just pytest tests/test_replay_tournament.py
just pytest-all
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add game/simulation/tournament.py tests/test_replay_tournament.py
git commit -m "feat(scripts): wire ReplayDB into simulate-tournament"
```

---

### Task 4: Wire ReplayDB into season.py

**Files:**

- Modify: `game/simulation/season.py`
- Create: `tests/test_replay_season.py`

**Interfaces:**

- Consumes: `ReplayDB` from Task 1; `run_series(record_seeds=, replay_seeds=)` from Task 2
- Produces:
  - `run_season(..., replaydb=None, week_num=1, recording=False)`
  - `main()` gains `--save-replay`, `--replay <path>`, `--save-leaderboard` flags

- [ ] **Step 1: Write failing tests**

```python
# tests/test_replay_season.py
from datetime import date


def _write_lb(path, tier="CH"):
    path.write_text(
        f"players:\n"
        f"  Alice:\n    tier: {tier}\n    display_name: Alice\n    github_username: ''\n    tier_stats: {{}}\n"
        f"  Bob:\n    tier: {tier}\n    display_name: Bob\n    github_username: ''\n    tier_stats: {{}}\n"
    )


def test_run_season_records_seeds(tmp_path):
    from game.simulation.replaydb import ReplayDB
    from game.simulation.season import run_season

    lb = tmp_path / "lb.yaml"
    _write_lb(lb)

    db = ReplayDB.create(tmp_path / "s.replay")
    db.save_meta("season", date(2026, 7, 13), "", 5, 4, {})

    run_season(n_games=5, top_n=4, lb_path=str(lb), replaydb=db, week_num=2, recording=True)
    seeds = db.get_seeds(week_num=2, tier="CH", series_idx=0)
    db.close()

    assert len(seeds) == 5


def test_run_season_replay_deterministic(tmp_path):
    from game.simulation.replaydb import ReplayDB
    from game.simulation.season import run_season

    lb = tmp_path / "lb.yaml"
    _write_lb(lb)

    replay_path = tmp_path / "s.replay"
    db_rec = ReplayDB.create(replay_path)
    db_rec.save_meta("season", date(2026, 7, 13), "", 20, 4, {})
    result_a = run_season(n_games=20, top_n=4, lb_path=str(lb), replaydb=db_rec, week_num=1, recording=True)
    db_rec.save_standings({})
    db_rec.close()

    _write_lb(lb)  # restore (season mutates lb)

    db_rep = ReplayDB.load(replay_path)
    result_b = run_season(n_games=20, top_n=4, lb_path=str(lb), replaydb=db_rep, week_num=1, recording=False)
    db_rep.close()

    assert result_b.get("CH") == result_a.get("CH")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
just pytest tests/test_replay_season.py
```

Expected: `TypeError` — `run_season()` doesn't accept `replaydb` yet.

- [ ] **Step 3: Update `run_season` signature in `game/simulation/season.py`**

Change the function signature (line 41):

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
```

For single-tier series (PRM, CH, inactive — the `else` branch around line 124), replace the `run_series` call with seed-aware version. `series_idx` is always `0` for single-tier series:

```python
            record_seeds: list[int] | None = [] if (replaydb is not None and recording) else None
            replay_seeds: list[int] | None = (
                replaydb.get_seeds(week_num, tier, 0)
                if (replaydb is not None and not recording)
                else None
            )
            result = run_series(
                players,
                n_games,
                tier=tier,
                on_game_complete=dashboard.update if dashboard else None,
                record_seeds=record_seeds,
                replay_seeds=replay_seeds,
            )
            if record_seeds is not None and replaydb is not None:
                for gn, seed in enumerate(record_seeds, 1):
                    replaydb.save_seed(week_num, tier, 0, gn, seed)
```

For L1 pool series (the `if tier == "L1" and len(players) > _POOL_MAX:` branch around line 104), replace each pool's `run_series` call. `series_idx` is the pool index `i`:

```python
            for i, pool_names in enumerate(pools_names):
                pool = [players_by_name[n] for n in pool_names if n in players_by_name]
                print(f"[run] L1 pool {i + 1}/{n_pools}: {pool_names}")
                if dashboard:
                    dashboard.start_series(f"L1 Pool {i + 1}")

                record_seeds: list[int] | None = [] if (replaydb is not None and recording) else None
                replay_seeds: list[int] | None = (
                    replaydb.get_seeds(week_num, tier, i)
                    if (replaydb is not None and not recording)
                    else None
                )
                result = run_series(
                    pool,
                    n_games,
                    on_game_complete=dashboard.update if dashboard else None,
                    record_seeds=record_seeds,
                    replay_seeds=replay_seeds,
                )
                if record_seeds is not None and replaydb is not None:
                    for gn, seed in enumerate(record_seeds, 1):
                        replaydb.save_seed(week_num, tier, i, gn, seed)
                if dashboard:
                    dashboard.on_series_complete(f"L1 Pool {i + 1}", result)
                wins.update(result.wins)
                pool_stats_list.append(result.stats)
```

- [ ] **Step 4: Update `main()` in `game/simulation/season.py`**

Add imports at top of file:

```python
import sys
from datetime import date
```

Add new args inside `main()` (after `--tui`):

```python
    parser.add_argument("--save-replay", action="store_true", default=False)
    parser.add_argument("--replay", type=Path, default=None)
    parser.add_argument("--save-leaderboard", action="store_true", default=False)
```

Add validation and replay setup after `args = parser.parse_args()`:

```python
    if args.save_replay and args.replay:
        print("[error] --save-replay and --replay are mutually exclusive", file=sys.stderr)
        sys.exit(1)
    if args.save_leaderboard and not args.replay:
        print("[error] --save-leaderboard requires --replay", file=sys.stderr)
        sys.exit(1)

    if args.date:
        os.environ["TODAY"] = args.date

    lb_path = os.environ.get("LEADERBOARD_PATH", "leaderboard.yaml")
    top_n = args.top_n
    step_date = date.fromisoformat(args.date) if args.date else date.today()

    from game.simulation.replaydb import ReplayDB

    replaydb = None
    recording = False
    temp_lb_path: str | None = None

    if args.save_replay:
        from game.season.utils import _load_lb

        replay_path = Path(f"sim-{step_date}.replay")
        replaydb = ReplayDB.create(replay_path)
        recording = True
        replaydb.save_meta(
            mode="season",
            step_date=step_date,
            quarter="",
            n_games=args.n_games,
            top_n=top_n,
            lb_snapshot=_load_lb(lb_path),
        )
    elif args.replay:
        import json
        import tempfile

        import yaml as _yaml

        replaydb = ReplayDB.load(args.replay)
        meta = replaydb.get_meta()
        lb_data = json.loads(meta["lb_snapshot"])
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
        _yaml.safe_dump(lb_data, tmp)
        tmp.close()
        temp_lb_path = tmp.name
        lb_path = temp_lb_path
        top_n = int(meta["top_n"])
        args.n_games = int(meta["n_games"])
        print(f"[replay] {args.replay} — season, {args.n_games} games/run")
```

Replace the existing `if args.tui: ... else: run_season(...)` block:

```python
    try:
        if args.tui:
            from game.components.utils import apply_display_names, import_player_classes_from_dir
            from game.season.utils import _load_lb
            from game.tui import TuiAdapter

            _all = import_player_classes_from_dir(str(_REPO_ROOT / "players"))
            apply_display_names(_all, _load_lb(lb_path).get("players", {}))
            display_names = {type(p).__name__: p.name for p in _all}
            adapter = TuiAdapter(n_games=args.n_games, display_names=display_names)
            adapter.run(
                lambda: run_season(
                    args.n_games, top_n, lb_path, dashboard=adapter,
                    replaydb=replaydb, week_num=1, recording=recording,
                )
            )
        else:
            run_season(
                args.n_games, top_n, lb_path,
                replaydb=replaydb, week_num=1, recording=recording,
            )

        if args.save_replay and replaydb:
            from game.season.utils import _load_lb

            replaydb.save_standings(_load_lb(lb_path).get("players", {}))
            replaydb.close()
            print(f"[done] Replay saved to sim-{step_date}.replay")

        if args.replay and replaydb:
            if args.save_leaderboard:
                import shutil

                real_lb = os.environ.get("LEADERBOARD_PATH", "leaderboard.yaml")
                shutil.copy(lb_path, real_lb)
                print("[done] Leaderboard updated from replay.")
            replaydb.close()

    finally:
        if temp_lb_path:
            os.unlink(temp_lb_path)
```

- [ ] **Step 5: Run tests**

```bash
just pytest tests/test_replay_season.py
just pytest-all
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add game/simulation/season.py tests/test_replay_season.py
git commit -m "feat(scripts): wire ReplayDB into simulate-season"
```

---

### Task 5: Wire ReplayDB into quarter.py

**Files:**

- Modify: `game/simulation/quarter.py`
- Modify: `tests/test_simulate_quarter.py` (add replay tests)

**Interfaces:**

- Consumes: `ReplayDB` (Task 1); `run_tournament`/`run_season` with `replaydb` params (Tasks 3–4)
- Produces:
  - `run_step(..., replaydb=None, week_num=1, recording=False)`
  - `parse_args()` returns namespace with `save_replay`, `replay`, `save_leaderboard`
  - `main()` orchestrates record/replay path with temp lb file

- [ ] **Step 1: Write failing tests**

Add to `tests/test_simulate_quarter.py`:

```python
def test_parse_args_save_replay_flag(monkeypatch):
    import sys
    from game.simulation.quarter import parse_args

    monkeypatch.setattr(sys, "argv", ["quarter.py", "--save-replay"])
    args = parse_args()
    assert args.save_replay is True
    assert args.replay is None


def test_parse_args_replay_flag(monkeypatch, tmp_path):
    import sys
    from game.simulation.quarter import parse_args

    replay_file = tmp_path / "sim.replay"
    replay_file.touch()
    monkeypatch.setattr(sys, "argv", ["quarter.py", "--replay", str(replay_file)])
    args = parse_args()
    assert args.replay == replay_file
    assert args.save_replay is False


def test_parse_args_save_leaderboard_flag(monkeypatch, tmp_path):
    import sys
    from game.simulation.quarter import parse_args

    replay_file = tmp_path / "sim.replay"
    replay_file.touch()
    monkeypatch.setattr(sys, "argv", [
        "quarter.py", "--replay", str(replay_file), "--save-leaderboard"
    ])
    args = parse_args()
    assert args.save_leaderboard is True


def test_run_step_passes_replaydb_to_tournament(monkeypatch):
    from game.simulation.quarter import run_step
    from datetime import date

    received = {}

    def fake_run_tournament(n_games, lb_path, dashboard=None, replaydb=None, week_num=1, recording=False):
        received["replaydb"] = replaydb
        received["week_num"] = week_num
        received["recording"] = recording
        print("ok")

    import sys
    fake_mod = type(sys)("game.simulation.tournament")
    fake_mod.run_tournament = fake_run_tournament
    monkeypatch.setitem(sys.modules, "game.simulation.tournament", fake_mod)

    sentinel = object()
    run_step(date(2026, 7, 6), "tournament", n_games=5, lb_path="lb.yaml",
             replaydb=sentinel, week_num=3, recording=True)
    assert received["replaydb"] is sentinel
    assert received["week_num"] == 3
    assert received["recording"] is True


def test_run_step_passes_replaydb_to_season(monkeypatch):
    from game.simulation.quarter import run_step
    from datetime import date

    received = {}

    def fake_run_season(n_games, top_n, lb_path, dashboard=None, replaydb=None, week_num=1, recording=False):
        received["replaydb"] = replaydb
        received["week_num"] = week_num
        print("ok")

    import sys
    fake_mod = type(sys)("game.simulation.season")
    fake_mod.run_season = fake_run_season
    monkeypatch.setitem(sys.modules, "game.simulation.season", fake_mod)

    sentinel = object()
    run_step(date(2026, 7, 13), "season", n_games=5, lb_path="lb.yaml",
             replaydb=sentinel, week_num=2)
    assert received["replaydb"] is sentinel
    assert received["week_num"] == 2
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
just pytest tests/test_simulate_quarter.py -k "replay or replaydb or save_replay or save_leaderboard"
```

Expected: failures on missing flag/param.

- [ ] **Step 3: Update `run_step` in `game/simulation/quarter.py`**

Update signature (line 32):

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
```

Inside the `with redirect_stdout(buf):` block, pass the new params through:

```python
        if mode == "tournament":
            from game.simulation.tournament import run_tournament

            run_tournament(n_games=n_games, lb_path=lb_path, dashboard=dashboard,
                           replaydb=replaydb, week_num=week_num, recording=recording)
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
```

- [ ] **Step 4: Update `parse_args` in `game/simulation/quarter.py`**

Add three new arguments after the existing `--tui` argument:

```python
    parser.add_argument(
        "--save-replay",
        action="store_true",
        default=False,
        help="Save seeds and initial state to a .replay file alongside the report.",
    )
    parser.add_argument(
        "--replay",
        type=Path,
        default=None,
        help="Path to a .replay file. Re-runs using stored seeds and leaderboard snapshot.",
    )
    parser.add_argument(
        "--save-leaderboard",
        action="store_true",
        default=False,
        help="When --replay is active, write the resulting leaderboard to leaderboard.yaml.",
    )
```

- [ ] **Step 5: Update `main()` in `game/simulation/quarter.py`**

Add `import sys` to the existing `import sys` inside `main()` — it's already there as a local import; move it to the top of `main()` before the validation block.

After `args = parse_args()`, add validation:

```python
    if args.save_replay and args.replay:
        print("[error] --save-replay and --replay are mutually exclusive", file=sys.stderr)
        sys.exit(1)
    if args.save_leaderboard and not args.replay:
        print("[error] --save-leaderboard requires --replay", file=sys.stderr)
        sys.exit(1)
```

After the validation block (currently `if not is_tournament_monday(args.start): ...`), wrap it to skip validation in replay mode:

```python
    from game.season.utils import is_tournament_monday

    if not args.replay and not is_tournament_monday(args.start):
        print(
            f"[error] {args.start} is not a tournament Monday "
            "(must be the first Monday of Jan/Apr/Jul/Oct).",
            file=sys.stderr,
        )
        sys.exit(1)
```

Add replay setup block after the validation:

```python
    from game.simulation.replaydb import ReplayDB

    replaydb = None
    recording = False
    temp_lb_path: str | None = None

    quarter = current_quarter(args.start)
    output_file = args.output or Path(f"sim-{quarter}.md")
    replay_path = Path(str(output_file).with_suffix(".replay"))
    lb_path = os.environ.get("LEADERBOARD_PATH", "leaderboard.yaml")

    if args.save_replay:
        from game.season.utils import _load_lb

        replaydb = ReplayDB.create(replay_path)
        recording = True
        replaydb.save_meta(
            mode="quarter",
            step_date=args.start,
            quarter=quarter,
            n_games=args.n_games,
            top_n=int(os.environ.get("TOP_N", "4")),
            lb_snapshot=_load_lb(lb_path),
        )
    elif args.replay:
        import json
        import tempfile

        import yaml as _yaml

        replaydb = ReplayDB.load(args.replay)
        meta = replaydb.get_meta()
        lb_data = json.loads(meta["lb_snapshot"])
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
        _yaml.safe_dump(lb_data, tmp)
        tmp.close()
        temp_lb_path = tmp.name
        lb_path = temp_lb_path
        quarter = meta["quarter"]
        n_games = int(meta["n_games"])
        os.environ["TOP_N"] = meta["top_n"]
        step_date = date.fromisoformat(meta["step_date"])
        mondays = compute_mondays(step_date)
        output_file = args.output or Path(f"sim-{quarter}.md")
        print(f"[replay] {args.replay} — quarter {quarter}, {n_games} games/run")
    else:
        n_games = args.n_games
        mondays = compute_mondays(args.start)
        step_date = args.start
```

Wrap the simulation loop in a `try/finally` and thread `replaydb`/`week_num`/`recording` through `run_step`. The loop currently reads:

```python
    steps: list[dict] = []
    t_total = time.perf_counter()

    if args.tui:
        ...
        def _run_quarter() -> None:
            ...
            for i, (step_date, mode) in enumerate(mondays):
                ...
                output = run_step(step_date, mode, args.n_games, lb_path, dashboard=adapter)
                ...
        adapter.run(_run_quarter)
    else:
        for i, (step_date, mode) in enumerate(mondays):
            ...
            output = run_step(step_date, mode, args.n_games, lb_path, dashboard=None)
```

Replace both `run_step` calls to include the new params. For the TUI branch, inside `_run_quarter()`:

```python
                output = run_step(
                    step_date, mode, n_games, lb_path,
                    dashboard=adapter,
                    replaydb=replaydb,
                    week_num=i + 1,
                    recording=recording,
                )
```

For the non-TUI branch:

```python
            output = run_step(
                step_date, mode, n_games, lb_path,
                replaydb=replaydb,
                week_num=i + 1,
                recording=recording,
            )
```

After the simulation loop, wrap cleanup in try/finally:

```python
    try:
        # ... (existing TUI/non-TUI simulation block) ...

        write_report(steps, lb_path, output_file, n_games)

        if args.save_replay and replaydb:
            from game.season.utils import _load_lb

            replaydb.save_standings(_load_lb(lb_path).get("players", {}))
            replaydb.close()
            print(f"[done] Replay saved to {replay_path}")

        if args.replay and replaydb:
            if args.save_leaderboard:
                import shutil

                real_lb = os.environ.get("LEADERBOARD_PATH", "leaderboard.yaml")
                shutil.copy(lb_path, real_lb)
                print("[done] Leaderboard updated from replay.")
            replaydb.close()

    finally:
        if temp_lb_path:
            os.unlink(temp_lb_path)

    print(f"[simulate] total elapsed: {time.perf_counter() - t_total:.1f}s")
```

- [ ] **Step 6: Run all tests**

```bash
just pytest-all
```

Expected: all pass including new quarter replay tests.

- [ ] **Step 7: Commit**

```bash
git add game/simulation/quarter.py tests/test_simulate_quarter.py
git commit -m "feat(scripts): wire ReplayDB into simulate-quarter with --save-replay and --replay flags"
```

---

### Task 6: Diff report (stretch goal)

**Files:**

- Modify: `game/simulation/quarter.py` (add `write_diff_report`, call it from `main()`)
- Create: `tests/test_replay_diff.py`

**Interfaces:**

- Consumes: `ReplayDB.get_meta()` from Task 1; final lb state from temp lb file (Task 5)
- Produces: `write_diff_report(original_standings, replay_lb_path, output_file) -> None`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_replay_diff.py
from pathlib import Path


def _write_lb(path, players_data: dict):
    import yaml

    path.write_text(yaml.safe_dump({"players": players_data}))


def test_write_diff_report_creates_file(tmp_path):
    from game.simulation.quarter import write_diff_report

    original = {
        "Alice": {
            "tier": "CH",
            "display_name": "Alice",
            "tier_stats": {"CH": {"wins": 40, "games": 100}},
        },
        "Bob": {
            "tier": "L1",
            "display_name": "Bob",
            "tier_stats": {"L1": {"wins": 30, "games": 100}},
        },
    }
    replay_lb = tmp_path / "lb.yaml"
    _write_lb(
        replay_lb,
        {
            "Alice": {
                "tier": "PRM",
                "display_name": "Alice",
                "tier_stats": {"PRM": {"wins": 55, "games": 100}},
            },
            "Bob": {
                "tier": "CH",
                "display_name": "Bob",
                "tier_stats": {"CH": {"wins": 35, "games": 100}},
            },
        },
    )
    out = tmp_path / "diff.md"
    write_diff_report(original, str(replay_lb), out)

    text = out.read_text()
    assert "Alice" in text
    assert "Bob" in text
    assert "CH" in text
    assert "PRM" in text


def test_write_diff_report_contains_delta(tmp_path):
    from game.simulation.quarter import write_diff_report

    original = {
        "Alice": {
            "tier": "CH",
            "display_name": "Alice",
            "tier_stats": {"CH": {"wins": 40, "games": 100}},
        },
    }
    replay_lb = tmp_path / "lb.yaml"
    _write_lb(
        replay_lb,
        {
            "Alice": {
                "tier": "CH",
                "display_name": "Alice",
                "tier_stats": {"CH": {"wins": 50, "games": 100}},
            },
        },
    )
    out = tmp_path / "diff.md"
    write_diff_report(original, str(replay_lb), out)

    text = out.read_text()
    assert "+10" in text or "10.0" in text
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
just pytest tests/test_replay_diff.py
```

Expected: `ImportError` — `write_diff_report` not defined yet.

- [ ] **Step 3: Add `write_diff_report` to `game/simulation/quarter.py`**

Add after `write_report()` (around line 102):

```python
def write_diff_report(
    original_standings: dict,
    replay_lb_path: str,
    output_file: Path,
) -> None:
    """Write a Markdown table comparing original vs replay per-player stats."""
    from game.season.utils import _load_lb

    replay_players = _load_lb(replay_lb_path).get("players", {})

    def _total_win_pct(player_data: dict) -> float:
        ts = player_data.get("tier_stats", {}).values()
        wins = sum(t.get("wins", 0) for t in ts)
        games = sum(t.get("games", 0) for t in ts)
        return round(wins / games * 100, 1) if games else 0.0

    all_names = sorted(set(original_standings) | set(replay_players))
    lines = [
        "# Replay Diff Report",
        "",
        "| Player | Orig Tier | Replay Tier | Orig Win% | Replay Win% | Delta |",
        "|--------|-----------|-------------|-----------|-------------|-------|",
    ]
    for name in all_names:
        orig = original_standings.get(name, {})
        repl = replay_players.get(name, {})
        display = orig.get("display_name") or repl.get("display_name") or name
        orig_tier = orig.get("tier", "—")
        repl_tier = repl.get("tier", "—")
        orig_pct = _total_win_pct(orig)
        repl_pct = _total_win_pct(repl)
        delta = round(repl_pct - orig_pct, 1)
        delta_str = f"+{delta}" if delta > 0 else str(delta)
        lines.append(
            f"| {display} | {orig_tier} | {repl_tier} | {orig_pct}% | {repl_pct}% | {delta_str}% |"
        )
    lines.append("")
    output_file.write_text("\n".join(lines))
    print(f"[done] Diff report written to {output_file}")
```

- [ ] **Step 4: Call `write_diff_report` from `main()` in replay mode**

Inside the replay cleanup block in `main()` (after `write_report(...)` is called, before `replaydb.close()`):

```python
        if args.replay and replaydb:
            meta = replaydb.get_meta()
            if "original_standings" in meta:
                import json

                original_standings = json.loads(meta["original_standings"])
                diff_file = Path(str(output_file).replace(".md", "-diff.md"))
                write_diff_report(original_standings, lb_path, diff_file)
            if args.save_leaderboard:
                import shutil

                real_lb = os.environ.get("LEADERBOARD_PATH", "leaderboard.yaml")
                shutil.copy(lb_path, real_lb)
                print("[done] Leaderboard updated from replay.")
            replaydb.close()
```

- [ ] **Step 5: Run all tests**

```bash
just pytest-all
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add game/simulation/quarter.py tests/test_replay_diff.py
git commit -m "feat(scripts): add replay diff report to simulate-quarter"
```
