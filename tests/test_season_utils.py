"""Tests for .github/scripts/season_utils.py shared utilities."""

import importlib.util
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).parent.parent
SCRIPT = REPO_ROOT / ".github" / "scripts" / "season_utils.py"


def _load():
    scripts_dir = str(SCRIPT.parent)
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    spec = importlib.util.spec_from_file_location("season_utils", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --- _load_lb ---


def test_load_lb_missing_file(tmp_path):
    mod = _load()
    result = mod._load_lb(str(tmp_path / "nonexistent.yaml"))
    assert result == {}


def test_load_lb_existing_file(tmp_path):
    lb = tmp_path / "leaderboard.yaml"
    lb.write_text("players:\n  Alice:\n    tier: CH\n")
    mod = _load()
    result = mod._load_lb(str(lb))
    assert result == {"players": {"Alice": {"tier": "CH"}}}


def test_load_lb_empty_file(tmp_path):
    lb = tmp_path / "leaderboard.yaml"
    lb.write_text("")
    mod = _load()
    result = mod._load_lb(str(lb))
    assert result == {}


# --- _save_lb ---


def test_save_lb_writes_yaml(tmp_path):
    mod = _load()
    lb = tmp_path / "leaderboard.yaml"
    data = {"players": {"Bob": {"tier": "L1"}}}
    mod._save_lb(data, str(lb))
    saved = yaml.safe_load(lb.read_text())
    assert saved["players"] == {"Bob": {"tier": "L1"}}
    assert "last_updated" in saved


def test_save_lb_sets_last_updated(tmp_path):
    mod = _load()
    lb = tmp_path / "leaderboard.yaml"
    mod._save_lb({}, str(lb))
    saved = yaml.safe_load(lb.read_text())
    assert saved["last_updated"].endswith("Z")
    assert "T" in saved["last_updated"]


def test_save_lb_round_trips(tmp_path):
    mod = _load()
    lb = tmp_path / "leaderboard.yaml"
    original = {"players": {"Carol": {"tier": "PRM", "wins": 7}}}
    mod._save_lb(original, str(lb))
    result = mod._load_lb(str(lb))
    assert result["players"] == original["players"]
