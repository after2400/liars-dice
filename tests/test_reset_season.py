"""Tests for .github/scripts/reset_season.py utility functions."""

import importlib.util
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
SCRIPT = REPO_ROOT / ".github" / "scripts" / "reset_season.py"


def _load():
    spec = importlib.util.spec_from_file_location("reset_season", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --- current_quarter ---


def test_current_quarter_q1():
    mod = _load()
    assert mod.current_quarter(date(2026, 1, 1)) == "2026-Q1"
    assert mod.current_quarter(date(2026, 3, 31)) == "2026-Q1"


def test_current_quarter_q2():
    mod = _load()
    assert mod.current_quarter(date(2026, 4, 1)) == "2026-Q2"
    assert mod.current_quarter(date(2026, 6, 30)) == "2026-Q2"


def test_current_quarter_q3():
    mod = _load()
    assert mod.current_quarter(date(2026, 7, 6)) == "2026-Q3"


def test_current_quarter_q4():
    mod = _load()
    assert mod.current_quarter(date(2026, 10, 5)) == "2026-Q4"


# --- is_tournament_monday ---


def test_is_tournament_monday_first_monday_q3():
    mod = _load()
    assert mod.is_tournament_monday(date(2026, 7, 6)) is True  # first Monday of July


def test_is_tournament_monday_second_monday_is_false():
    mod = _load()
    assert mod.is_tournament_monday(date(2026, 7, 13)) is False


def test_is_tournament_monday_non_monday_is_false():
    mod = _load()
    assert mod.is_tournament_monday(date(2026, 7, 7)) is False  # Tuesday


def test_is_tournament_monday_first_monday_q4():
    mod = _load()
    assert mod.is_tournament_monday(date(2026, 10, 5)) is True  # first Monday of October


def test_is_tournament_monday_regular_monday():
    mod = _load()
    assert mod.is_tournament_monday(date(2026, 6, 8)) is False  # Monday but not quarter-start


# --- form_pools ---


def test_form_pools_single_pool():
    mod = _load()
    pools = mod.form_pools(["A", "B", "C", "D"], 1)
    assert pools == [["A", "B", "C", "D"]]


def test_form_pools_two_pools_s_curve():
    mod = _load()
    # S-curve: 6 players into 2 pools
    # idx: 0→pool0, 1→pool1, 2→pool1, 3→pool0, 4→pool0, 5→pool1
    pools = mod.form_pools(["A", "B", "C", "D", "E", "F"], 2)
    assert len(pools) == 2
    assert "A" in pools[0]
    assert "B" in pools[1]
    assert "C" in pools[1]  # serpentine reverses at right edge
    assert "D" in pools[0]


def test_form_pools_sizes_differ_by_at_most_one():
    mod = _load()
    pools = mod.form_pools(list("ABCDEFGHIJK"), 2)  # 11 players, 2 pools
    sizes = [len(p) for p in pools]
    assert max(sizes) - min(sizes) <= 1


def test_form_pools_all_players_present():
    mod = _load()
    players = [f"P{i}" for i in range(11)]
    pools = mod.form_pools(players, 2)
    assert sorted(sum(pools, [])) == sorted(players)
