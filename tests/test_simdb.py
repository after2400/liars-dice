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
    tables = {
        r[0]
        for r in db._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    }
    assert tables == {"series", "h2h", "challenge_by_face"}


def test_insert_series_writes_series_row():
    from game.components.series import SeriesResult
    from game.tui.simdb import SimDB

    stats = _make_stats("Oracle")
    result = SeriesResult(wins={"Oracle": 40, "EvilStewie": 60}, stats=stats, tier="CH")
    db = SimDB()
    db.insert_series("Week 1", "CH", result)
    row = db._conn.execute(
        "SELECT step_label, tier, wins, games, rounds, penalties FROM series WHERE player='Oracle'"
    ).fetchone()
    assert row == ("Week 1", "CH", 40, 100, 1000, 2)


def test_insert_series_writes_h2h_rows():
    from game.components.series import SeriesResult
    from game.tui.simdb import SimDB

    stats = _make_stats("Oracle")
    stats._die_losses_from_bluff["Oracle"]["EvilStewie"] = 15
    stats._die_losses_from_challenge["Oracle"]["EvilStewie"] = 10
    stats._die_losses_from_bluff["EvilStewie"]["Oracle"] = 8
    result = SeriesResult(wins={"Oracle": 40, "EvilStewie": 60}, stats=stats, tier="CH")
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
    result = SeriesResult(wins={"Oracle": 40, "EvilStewie": 60}, stats=stats, tier="CH")
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
