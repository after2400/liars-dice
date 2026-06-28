from datetime import date

import pytest


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
    db.save_seeds(week_num=1, tier="PRM", series_idx=0, seeds=[111, 222, 333])
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


def test_load_missing_file_raises(tmp_path):
    import sqlite3

    from game.simulation.replaydb import ReplayDB

    with pytest.raises(sqlite3.OperationalError):
        ReplayDB.load(tmp_path / "nonexistent.replay")


def test_save_seeds_from_background_thread(tmp_path):
    """ReplayDB connections must be usable from threads other than the creator thread.

    The TUI runs the simulation in a daemon thread; save_seeds and get_seeds are
    both called from that thread. Without check_same_thread=False, sqlite3 raises
    ProgrammingError and replay silently produces nothing.
    """
    import threading

    from game.simulation.replaydb import ReplayDB

    path = tmp_path / "threaded.replay"
    db = ReplayDB.create(path)
    db.save_meta("quarter", date(2026, 7, 6), "2026-Q3", 50, 4, {})

    errors: list[Exception] = []

    def _worker() -> None:
        try:
            db.save_seeds(1, None, 0, [101, 202, 303])
        except Exception as exc:
            errors.append(exc)

    t = threading.Thread(target=_worker)
    t.start()
    t.join()

    assert not errors, f"save_seeds raised from thread: {errors[0]}"
    seeds = db.get_seeds(1, None, 0)
    db.close()
    assert seeds == [101, 202, 303]


def test_get_seeds_from_background_thread(tmp_path):
    import threading

    from game.simulation.replaydb import ReplayDB

    path = tmp_path / "threaded_load.replay"
    db = ReplayDB.create(path)
    db.save_seeds(1, "PRM", 0, [10, 20, 30])
    db.close()

    db2 = ReplayDB.load(path)
    result: list[list[int]] = []
    errors: list[Exception] = []

    def _worker() -> None:
        try:
            result.append(db2.get_seeds(1, "PRM", 0))
        except Exception as exc:
            errors.append(exc)

    t = threading.Thread(target=_worker)
    t.start()
    t.join()

    db2.close()
    assert not errors, f"get_seeds raised from thread: {errors[0]}"
    assert result == [[10, 20, 30]]


def test_save_and_get_seeds_large_unsigned(tmp_path):
    from game.simulation.replaydb import ReplayDB

    db = ReplayDB.create(tmp_path / "test.replay")
    big_seed = 2**64 - 1  # max unsigned 64-bit
    db.save_seeds(1, None, 0, [big_seed])
    result = db.get_seeds(1, None, 0)
    assert result == [big_seed]
    db.close()
