"""Tests for game/season/utils.py shared utilities."""

from datetime import date

import yaml

from game.season.utils import (
    _load_lb,
    _save_lb,
    next_tournament_monday,
)

# --- _load_lb ---


def test_load_lb_missing_file(tmp_path):
    result = _load_lb(str(tmp_path / "nonexistent.yaml"))
    assert result == {}


def test_load_lb_existing_file(tmp_path):
    lb = tmp_path / "leaderboard.yaml"
    lb.write_text("players:\n  Alice:\n    tier: CH\n")
    result = _load_lb(str(lb))
    assert result == {"players": {"Alice": {"tier": "CH"}}}


def test_load_lb_empty_file(tmp_path):
    lb = tmp_path / "leaderboard.yaml"
    lb.write_text("")
    result = _load_lb(str(lb))
    assert result == {}


# --- _save_lb ---


def test_save_lb_writes_yaml(tmp_path):
    lb = tmp_path / "leaderboard.yaml"
    data = {"players": {"Bob": {"tier": "L1"}}}
    _save_lb(data, str(lb))
    saved = yaml.safe_load(lb.read_text())
    assert saved["players"] == {"Bob": {"tier": "L1"}}
    assert "last_updated" in saved


def test_save_lb_sets_last_updated(tmp_path):
    lb = tmp_path / "leaderboard.yaml"
    _save_lb({}, str(lb))
    saved = yaml.safe_load(lb.read_text())
    assert saved["last_updated"].endswith("Z")
    assert "T" in saved["last_updated"]


def test_save_lb_round_trips(tmp_path):
    lb = tmp_path / "leaderboard.yaml"
    original = {"players": {"Carol": {"tier": "PRM", "wins": 7}}}
    _save_lb(original, str(lb))
    result = _load_lb(str(lb))
    assert result["players"] == original["players"]


# --- next_tournament_monday ---


def test_next_tournament_monday_on_tournament_day():
    # 2026-07-06 is the first Monday of Q3 — should return itself
    result = next_tournament_monday(date(2026, 7, 6))
    assert result == date(2026, 7, 6)


def test_next_tournament_monday_before_quarter():
    # Mid-June: next tournament Monday is the first Monday of Q3
    result = next_tournament_monday(date(2026, 6, 15))
    assert result == date(2026, 7, 6)


def test_next_tournament_monday_day_after():
    # 2026-07-07 (Tuesday after Q3 tournament): next is Q4, first Monday of October
    result = next_tournament_monday(date(2026, 7, 7))
    assert result == date(2026, 10, 5)
