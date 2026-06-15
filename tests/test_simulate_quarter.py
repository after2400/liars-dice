"""Tests for game/simulation/quarter.py."""

from datetime import date


def test_compute_mondays_q3_2026():
    from game.simulation.quarter import compute_mondays

    result = compute_mondays(date(2026, 7, 6))
    assert len(result) == 13
    assert result[0] == (date(2026, 7, 6), "tournament")
    assert result[1] == (date(2026, 7, 13), "season")
    assert result[-1] == (date(2026, 9, 28), "season")


def test_compute_mondays_first_is_always_tournament():
    from game.simulation.quarter import compute_mondays

    result = compute_mondays(date(2026, 7, 6))
    assert result[0][1] == "tournament"
    for _, mode in result[1:]:
        assert mode == "season"


def test_compute_mondays_q4_2026():
    from game.simulation.quarter import compute_mondays

    result = compute_mondays(date(2026, 10, 5))
    assert result[0] == (date(2026, 10, 5), "tournament")
    assert result[-1] == (date(2026, 12, 28), "season")
    assert len(result) == 13


def test_compute_mondays_all_mondays():
    from game.simulation.quarter import compute_mondays

    result = compute_mondays(date(2026, 7, 6))
    for d, _ in result:
        assert d.weekday() == 0  # Monday


def test_run_step_sets_dry_run(monkeypatch):
    from game.simulation.quarter import run_step

    calls = []

    class FakeProc:
        stdout = iter(["[dry-run] would post\n"])
        returncode = 0

        def wait(self):
            pass

    def fake_popen(cmd, **kwargs):
        calls.append(kwargs.get("env", {}))
        return FakeProc()

    monkeypatch.setattr("game.simulation.quarter.subprocess.Popen", fake_popen)
    run_step(date(2026, 7, 6), "tournament", n_games=50, lb_path="leaderboard.yaml")

    assert calls[0]["DRY_RUN"] == "true"


def test_run_step_sets_today(monkeypatch):
    from game.simulation.quarter import run_step

    calls = []

    class FakeProc:
        stdout = iter([])
        returncode = 0

        def wait(self):
            pass

    def fake_popen(cmd, **kwargs):
        calls.append(kwargs.get("env", {}))
        return FakeProc()

    monkeypatch.setattr("game.simulation.quarter.subprocess.Popen", fake_popen)
    run_step(date(2026, 7, 13), "season", n_games=50, lb_path="leaderboard.yaml")

    assert calls[0]["TODAY"] == "2026-07-13"


def test_run_step_calls_correct_script(monkeypatch):
    from game.simulation.quarter import run_step

    cmds = []

    class FakeProc:
        stdout = iter([])
        returncode = 0

        def wait(self):
            pass

    def fake_popen(cmd, **kwargs):
        cmds.append(cmd)
        return FakeProc()

    monkeypatch.setattr("game.simulation.quarter.subprocess.Popen", fake_popen)

    run_step(date(2026, 7, 6), "tournament", n_games=50, lb_path="leaderboard.yaml")
    assert "reset_season.py" in cmds[-1][-1]

    run_step(date(2026, 7, 13), "season", n_games=50, lb_path="leaderboard.yaml")
    assert "run_season.py" in cmds[-1][-1]


def test_run_step_returns_captured_output(monkeypatch):
    from game.simulation.quarter import run_step

    class FakeProc:
        stdout = iter(["line one\n", "line two\n"])
        returncode = 0

        def wait(self):
            pass

    monkeypatch.setattr(
        "game.simulation.quarter.subprocess.Popen",
        lambda *a, **kw: FakeProc(),
    )

    output = run_step(date(2026, 7, 6), "tournament", n_games=50, lb_path="leaderboard.yaml")
    assert "line one" in output
    assert "line two" in output
