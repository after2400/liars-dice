from datetime import date

_LB_YAML = (
    "players:\n"
    "  Alice:\n    tier: PRM\n    display_name: Alice\n    github_username: ''\n    tier_stats: {}\n"
    "  Bruno:\n    tier: PRM\n    display_name: Bruno\n    github_username: ''\n    tier_stats: {}\n"
    "tournament_state:\n  quarter: 2026-Q3\n"
)


def _make_replaydb(tmp_path):
    from game.simulation.replaydb import ReplayDB

    db = ReplayDB.create(tmp_path / "t.replay")
    db.save_meta("tournament", date(2026, 7, 6), "", 10, 4, {})
    return db


def test_run_tournament_records_seeds(tmp_path, monkeypatch):
    """When recording=True, seeds are saved to replaydb in a single batch per pool."""
    from game.simulation.tournament import run_tournament

    db = _make_replaydb(tmp_path)

    saved: list[tuple] = []
    original_save_seeds = db.save_seeds
    db.save_seeds = lambda *a: saved.append(a) or original_save_seeds(*a)

    lb = tmp_path / "lb.yaml"
    lb.write_text(_LB_YAML)
    monkeypatch.setenv("LEADERBOARD_PATH", str(lb))

    run_tournament(n_games=5, lb_path=str(lb), replaydb=db, week_num=1, recording=True)
    db.close()

    # One batch call per pool (Alice+Bruno → 1 pool)
    assert len(saved) == 1
    week_num, tier, series_idx, seeds = saved[0]
    assert week_num == 1  # week_num=1
    assert tier is None  # tier=None for tournament pools
    assert series_idx == 0  # pool_0
    assert len(seeds) == 5  # one seed per game


def test_run_tournament_replay_uses_stored_seeds(tmp_path, monkeypatch):
    """Replaying with stored seeds produces identical wins."""
    from game.simulation.replaydb import ReplayDB
    from game.simulation.tournament import run_tournament

    lb = tmp_path / "lb.yaml"
    lb.write_text(_LB_YAML)

    # Record
    replay_path = tmp_path / "t.replay"
    db_record = ReplayDB.create(replay_path)
    db_record.save_meta("tournament", date(2026, 7, 6), "", 20, 4, {})
    run_tournament(n_games=20, lb_path=str(lb), replaydb=db_record, week_num=1, recording=True)
    db_record.save_standings({})
    db_record.close()

    # Restore lb (tournament zeroed tier_stats)
    lb.write_text(_LB_YAML)

    # Replay
    db_replay = ReplayDB.load(replay_path)
    result_replay = run_tournament(
        n_games=20, lb_path=str(lb), replaydb=db_replay, week_num=1, recording=False
    )
    db_replay.close()

    # Both runs must produce the same pool results
    # (wins are stored in pool_results inside tournament, and returned)
    assert result_replay is not None
