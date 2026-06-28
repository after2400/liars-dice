from datetime import date


def _write_lb(path, tier="CH"):
    path.write_text(
        f"players:\n"
        f"  Alice:\n    tier: {tier}\n    display_name: Alice\n    github_username: ''\n    tier_stats: {{}}\n"
        f"  Bruno:\n    tier: {tier}\n    display_name: Bruno\n    github_username: ''\n    tier_stats: {{}}\n"
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
    result_a = run_season(
        n_games=20, top_n=4, lb_path=str(lb), replaydb=db_rec, week_num=1, recording=True
    )
    db_rec.save_standings({})
    db_rec.close()

    _write_lb(lb)  # restore (season mutates lb)

    db_rep = ReplayDB.load(replay_path)
    result_b = run_season(
        n_games=20, top_n=4, lb_path=str(lb), replaydb=db_rep, week_num=1, recording=False
    )
    db_rep.close()

    assert result_b.get("CH") == result_a.get("CH")
