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
