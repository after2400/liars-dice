"""Tests for game/simulation/quarter.py."""

import os
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


def test_write_report_contains_quarter_header(tmp_path):
    from game.simulation.quarter import write_report

    lb = tmp_path / "leaderboard.yaml"
    lb.write_text(
        "players:\n  Diego:\n    tier: PRM\n    display_name: Diego\n    github_username: ''\n    tier_stats:\n      PRM:\n        wins: 100\n        games: 200\n        win_pct: 50.0\n"
    )
    out = tmp_path / "report.md"

    steps = [
        {"date": date(2026, 7, 6), "mode": "tournament", "output": "[done] tournament\n"},
        {"date": date(2026, 7, 13), "mode": "season", "output": "[done] season\n"},
    ]
    write_report(steps, str(lb), out, n_games=50)

    text = out.read_text()
    assert "2026-Q3" in text


def test_write_report_contains_monday_sections(tmp_path):
    from game.simulation.quarter import write_report

    lb = tmp_path / "leaderboard.yaml"
    lb.write_text("players: {}\n")
    out = tmp_path / "report.md"

    steps = [
        {"date": date(2026, 7, 6), "mode": "tournament", "output": "tournament output\n"},
        {"date": date(2026, 7, 13), "mode": "season", "output": "season output\n"},
    ]
    write_report(steps, str(lb), out, n_games=50)

    text = out.read_text()
    assert "2026-07-06" in text
    assert "Tournament" in text
    assert "2026-07-13" in text
    assert "Week 1" in text
    assert "tournament output" in text
    assert "season output" in text


def test_write_report_contains_final_standings(tmp_path):
    from game.simulation.quarter import write_report

    lb = tmp_path / "leaderboard.yaml"
    lb.write_text(
        "players:\n"
        "  Diego:\n"
        "    tier: PRM\n"
        "    display_name: Diego\n"
        "    github_username: ''\n"
        "    tier_stats:\n"
        "      PRM:\n"
        "        wins: 100\n"
        "        games: 200\n"
        "        win_pct: 50.0\n"
    )
    out = tmp_path / "report.md"
    write_report([], str(lb), out, n_games=50)

    text = out.read_text()
    assert "Final Standings" in text
    assert "Premier" in text
    assert "Diego" in text


def test_parse_args_defaults(monkeypatch):
    import sys

    from game.season.utils import next_tournament_monday
    from game.simulation.quarter import parse_args

    monkeypatch.setattr(sys, "argv", ["quarter.py"])
    args = parse_args()

    assert args.n_games == int(os.environ.get("N_GAMES", "1000"))
    assert args.start == next_tournament_monday()
    assert args.output is None


def test_parse_args_start_override(monkeypatch):
    import sys

    from game.simulation.quarter import parse_args

    monkeypatch.setattr(sys, "argv", ["quarter.py", "--start", "2026-07-06"])
    args = parse_args()
    assert args.start == date(2026, 7, 6)


def test_parse_args_n_games_override(monkeypatch):
    import sys

    from game.simulation.quarter import parse_args

    monkeypatch.setattr(sys, "argv", ["quarter.py", "--n-games", "50"])
    args = parse_args()
    assert args.n_games == 50
