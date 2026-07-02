import pytest


def test_unknown_player_has_zero_defaults():
    from game.components.perf import PerfTracker

    tracker = PerfTracker()
    assert tracker.call_count("Nobody") == 0
    assert tracker.avg_wall_ms("Nobody") == 0.0
    assert tracker.max_wall_ms("Nobody") == 0.0
    assert tracker.p95_wall_ms("Nobody") == 0.0
    assert tracker.avg_cpu_ms("Nobody") == 0.0
    assert tracker.max_cpu_ms("Nobody") == 0.0


def test_tracked_players_empty_for_new_tracker():
    from game.components.perf import PerfTracker

    assert PerfTracker().tracked_players == []


def test_time_call_records_one_sample(monkeypatch):
    import game.components.perf as perf_mod

    wall = iter([0.0, 0.010])
    cpu = iter([0.0, 0.004])
    monkeypatch.setattr(perf_mod.time, "perf_counter", lambda: next(wall))
    monkeypatch.setattr(perf_mod.time, "thread_time", lambda: next(cpu))

    tracker = perf_mod.PerfTracker()
    with tracker.time_call("Alice"):
        pass

    assert tracker.call_count("Alice") == 1
    assert tracker.tracked_players == ["Alice"]
    assert tracker.avg_wall_ms("Alice") == pytest.approx(10.0)
    assert tracker.avg_cpu_ms("Alice") == pytest.approx(4.0)


def test_time_call_records_sample_even_when_body_raises(monkeypatch):
    import game.components.perf as perf_mod

    wall = iter([0.0, 0.005])
    cpu = iter([0.0, 0.002])
    monkeypatch.setattr(perf_mod.time, "perf_counter", lambda: next(wall))
    monkeypatch.setattr(perf_mod.time, "thread_time", lambda: next(cpu))

    tracker = perf_mod.PerfTracker()
    with pytest.raises(RuntimeError):
        with tracker.time_call("Crasher"):
            raise RuntimeError("boom")

    assert tracker.call_count("Crasher") == 1
    assert tracker.avg_wall_ms("Crasher") == pytest.approx(5.0)


def test_avg_and_max_wall_ms_across_three_calls(monkeypatch):
    import game.components.perf as perf_mod

    # elapsed per call: 10ms, 20ms, 30ms
    wall = iter([0.000, 0.010, 0.010, 0.030, 0.030, 0.060])
    cpu = iter([0.0] * 6)
    monkeypatch.setattr(perf_mod.time, "perf_counter", lambda: next(wall))
    monkeypatch.setattr(perf_mod.time, "thread_time", lambda: next(cpu))

    tracker = perf_mod.PerfTracker()
    for _ in range(3):
        with tracker.time_call("Bruno"):
            pass

    assert tracker.call_count("Bruno") == 3
    assert tracker.avg_wall_ms("Bruno") == pytest.approx(20.0)
    assert tracker.max_wall_ms("Bruno") == pytest.approx(30.0)


def test_total_wall_s_and_total_cpu_s_sum_across_calls(monkeypatch):
    import game.components.perf as perf_mod

    # elapsed per call: wall 10ms, 20ms, 30ms; cpu 1ms, 2ms, 3ms
    wall = iter([0.000, 0.010, 0.010, 0.030, 0.030, 0.060])
    cpu = iter([0.000, 0.001, 0.001, 0.003, 0.003, 0.006])
    monkeypatch.setattr(perf_mod.time, "perf_counter", lambda: next(wall))
    monkeypatch.setattr(perf_mod.time, "thread_time", lambda: next(cpu))

    tracker = perf_mod.PerfTracker()
    for _ in range(3):
        with tracker.time_call("Bruno"):
            pass

    assert tracker.total_wall_s("Bruno") == pytest.approx(0.060)
    assert tracker.total_cpu_s("Bruno") == pytest.approx(0.006)


def test_total_wall_s_and_total_cpu_s_zero_for_unknown_player():
    from game.components.perf import PerfTracker

    tracker = PerfTracker()
    assert tracker.total_wall_s("Nobody") == 0.0
    assert tracker.total_cpu_s("Nobody") == 0.0


def test_p95_wall_ms_nearest_rank(monkeypatch):
    import game.components.perf as perf_mod

    # 20 calls with elapsed 1ms..20ms
    wall = iter([v for k in range(1, 21) for v in (0.0, k * 0.001)])
    cpu = iter([0.0] * 40)
    monkeypatch.setattr(perf_mod.time, "perf_counter", lambda: next(wall))
    monkeypatch.setattr(perf_mod.time, "thread_time", lambda: next(cpu))

    tracker = perf_mod.PerfTracker()
    for _ in range(20):
        with tracker.time_call("Carol"):
            pass

    assert tracker.p95_wall_ms("Carol") == pytest.approx(19.0)
    assert tracker.max_wall_ms("Carol") == pytest.approx(20.0)
    assert tracker.avg_wall_ms("Carol") == pytest.approx(sum(range(1, 21)) / 20)


def test_peak_memory_none_when_profiling_disabled():
    from game.components.perf import PerfTracker

    tracker = PerfTracker()  # profile_memory defaults to False
    with tracker.time_call("Alice"):
        pass

    assert tracker.avg_peak_kb("Alice") is None
    assert tracker.max_peak_kb("Alice") is None


def test_peak_memory_recorded_when_profiling_enabled():
    from game.components.perf import PerfTracker

    tracker = PerfTracker(profile_memory=True)
    with tracker.time_call("Allocator"):
        _ = [0] * 200_000  # list's own backing array is well above any noise floor

    avg_kb = tracker.avg_peak_kb("Allocator")
    assert avg_kb is not None
    assert avg_kb > 50  # generous floor; real allocation is ~1.6MB


def test_peak_memory_excludes_preexisting_baseline_allocation():
    """A call's peak must reflect only its own allocation, not memory that
    was already alive in the process before the call started (e.g. state
    accumulated over prior games)."""
    from game.components.perf import PerfTracker

    tracker = PerfTracker(profile_memory=True)
    # Simulate several MB of state already alive before this call — without
    # baseline subtraction, that memory leaks into every subsequent peak
    # reading regardless of what the timed call itself allocates.
    baseline_junk = [0] * 5_000_000
    with tracker.time_call("Alice"):
        _ = [0] * 1000  # tiny allocation relative to baseline_junk

    avg_kb = tracker.avg_peak_kb("Alice")
    assert avg_kb is not None
    assert avg_kb < 500  # this call's own allocation is a few KB, not tens of MB
    del baseline_junk


def test_format_perf_empty_tracker_returns_empty_string():
    from game.components.perf import PerfTracker
    from game.components.series import format_perf

    assert format_perf(PerfTracker(), n_games=10) == ""


def test_format_perf_includes_all_tracked_players(monkeypatch):
    import game.components.perf as perf_mod
    from game.components.series import format_perf

    wall = iter([0.0, 0.010, 0.0, 0.020])
    cpu = iter([0.0] * 4)
    monkeypatch.setattr(perf_mod.time, "perf_counter", lambda: next(wall))
    monkeypatch.setattr(perf_mod.time, "thread_time", lambda: next(cpu))

    tracker = perf_mod.PerfTracker()
    with tracker.time_call("Alice"):
        pass
    with tracker.time_call("Bruno"):
        pass

    output = format_perf(tracker, n_games=5)
    assert "Alice" in output
    assert "Bruno" in output
    assert "Player Performance" in output
    assert "TotalWall(s)" in output
    assert "TotalCPU(s)" in output


def test_format_perf_sorts_slowest_first(monkeypatch):
    import game.components.perf as perf_mod
    from game.components.series import format_perf

    # Alice: 10ms, Bruno: 30ms
    wall = iter([0.0, 0.010, 0.0, 0.030])
    cpu = iter([0.0] * 4)
    monkeypatch.setattr(perf_mod.time, "perf_counter", lambda: next(wall))
    monkeypatch.setattr(perf_mod.time, "thread_time", lambda: next(cpu))

    tracker = perf_mod.PerfTracker()
    with tracker.time_call("Alice"):
        pass
    with tracker.time_call("Bruno"):
        pass

    output = format_perf(tracker, n_games=5)
    assert output.index("Bruno") < output.index("Alice")


def test_format_perf_omits_memory_columns_when_disabled(monkeypatch):
    import game.components.perf as perf_mod
    from game.components.series import format_perf

    monkeypatch.setattr(perf_mod.time, "perf_counter", lambda: 0.0)
    monkeypatch.setattr(perf_mod.time, "thread_time", lambda: 0.0)

    tracker = perf_mod.PerfTracker(profile_memory=False)
    with tracker.time_call("Alice"):
        pass

    assert "Peak" not in format_perf(tracker, n_games=1)


def test_format_perf_includes_memory_columns_when_enabled():
    from game.components.perf import PerfTracker
    from game.components.series import format_perf

    tracker = PerfTracker(profile_memory=True)
    with tracker.time_call("Alice"):
        _ = [0] * 1000

    assert "Peak" in format_perf(tracker, n_games=1)


def test_run_season_profile_memory_prints_perf_table(tmp_path, capsys):
    from game.simulation.season import run_season

    lb = tmp_path / "lb.yaml"
    lb.write_text(
        "players:\n"
        "  Alice:\n    tier: CH\n    display_name: Alice\n    github_username: ''\n    tier_stats: {}\n"
        "  Bruno:\n    tier: CH\n    display_name: Bruno\n    github_username: ''\n    tier_stats: {}\n"
    )

    run_season(n_games=3, top_n=4, lb_path=str(lb), week_num=1, profile_memory=True)

    output = capsys.readouterr().out
    assert "Player Performance" in output
    assert "Peak" in output


def test_run_season_default_profile_memory_off(tmp_path, capsys):
    from game.simulation.season import run_season

    lb = tmp_path / "lb.yaml"
    lb.write_text(
        "players:\n"
        "  Alice:\n    tier: CH\n    display_name: Alice\n    github_username: ''\n    tier_stats: {}\n"
        "  Bruno:\n    tier: CH\n    display_name: Bruno\n    github_username: ''\n    tier_stats: {}\n"
    )

    run_season(n_games=3, top_n=4, lb_path=str(lb), week_num=1)

    output = capsys.readouterr().out
    assert "Player Performance" in output
    assert "Peak" not in output


def test_run_tournament_profile_memory_prints_perf_table(tmp_path, capsys):
    from game.simulation.tournament import run_tournament

    lb = tmp_path / "lb.yaml"
    lb.write_text(
        "players:\n"
        "  Alice:\n    tier: CH\n    display_name: Alice\n    github_username: ''\n    tier_stats: {}\n"
        "  Bruno:\n    tier: CH\n    display_name: Bruno\n    github_username: ''\n    tier_stats: {}\n"
    )

    run_tournament(n_games=3, lb_path=str(lb), week_num=1, profile_memory=True)

    output = capsys.readouterr().out
    assert "Player Performance" in output
    assert "Peak" in output
