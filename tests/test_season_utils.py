"""Tests for game/season/utils.py shared utilities."""

from datetime import date

import yaml

from game.season.utils import (
    _load_lb,
    _save_lb,
    expel_player,
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


# --- expel_player ---
#
# Shared by both run_season.py (regular Monday tiers) and reset_season.py
# (quarterly tournament pools), so it's tested once, here, directly.


def _make_fake_repo(tmp_path, name="fake_repo") -> tuple:
    repo = tmp_path / name
    (repo / "players").mkdir(parents=True)
    player_file = repo / "players" / "cheater.py"
    player_file.write_text("class Cheater:\n    name = 'Cheater'\n")
    return repo, player_file


def test_expel_player_skips_non_live_leaderboard(tmp_path):
    """A tmp/test leaderboard path must never trigger real file deletion."""
    repo, player_file = _make_fake_repo(tmp_path)
    isolated_lb = tmp_path / "isolated_lb.yaml"
    isolated_lb.write_text("players:\n  Cheater:\n    tier: L1\n")

    expel_player(str(isolated_lb), "Cheater", repo, dry_run=False)

    assert player_file.exists(), "Player file must not be deleted for a non-live leaderboard"
    data = yaml.safe_load(isolated_lb.read_text())
    assert "Cheater" in data["players"], "Leaderboard must not be mutated for a non-live path"


def test_expel_player_skips_when_dry_run(tmp_path):
    """Local `just simulate-*` commands set dry_run=True but use the real
    leaderboard.yaml path — dry_run must be checked independently of the
    path, or a local simulation would delete a real players/*.py file."""
    repo, player_file = _make_fake_repo(tmp_path, "fake_repo_dry")
    # Deliberately the *live* path (matches repo_root) — dry_run alone must stop it.
    live_lb = repo / "leaderboard.yaml"
    live_lb.write_text("players:\n  Cheater:\n    tier: L1\n")

    expel_player(str(live_lb), "Cheater", repo, dry_run=True)

    assert player_file.exists(), "Player file must not be deleted during a dry run"
    data = yaml.safe_load(live_lb.read_text())
    assert "Cheater" in data["players"], "Leaderboard must not be mutated during a dry run"


def test_expel_player_removes_offender_from_live_leaderboard(tmp_path):
    """Against the real, live leaderboard path with dry_run off, expulsion
    deletes the offender only."""
    repo, player_file = _make_fake_repo(tmp_path, "fake_repo_live")
    live_lb = repo / "leaderboard.yaml"
    live_lb.write_text("players:\n  Cheater:\n    tier: L1\n  Honest:\n    tier: L1\n")

    expel_player(str(live_lb), "Cheater", repo, dry_run=False)

    assert not player_file.exists(), "Offender's player file should be deleted"
    data = yaml.safe_load(live_lb.read_text())
    assert "Cheater" not in data["players"]
    assert "Honest" in data["players"]
