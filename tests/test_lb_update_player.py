import os
import subprocess
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).parent.parent
SCRIPT = REPO_ROOT / ".github/scripts/lb_update_player.py"


def _run(player_file: Path, lb: dict, tmp_path: Path) -> subprocess.CompletedProcess:
    lb_path = tmp_path / "leaderboard.yaml"
    lb_path.write_text(yaml.dump(lb, default_flow_style=False, sort_keys=False))
    return subprocess.run(
        ["uv", "run", "python", str(SCRIPT), str(player_file)],
        cwd=str(tmp_path),
        env={**os.environ},
        capture_output=True,
        text=True,
    )


def _base_lb() -> dict:
    return {
        "players": {
            "Topper": {
                "display_name": "Topper",
                "github_username": "alice",
                "tier": "L1",
                "tier_since": "2026-01-01T00:00:00Z",
                "date_added": "2026-01-01T00:00:00Z",
                "times_inactive": 0,
                "tier_stats": {},
            }
        }
    }


def test_sets_avatar_on_new_attribute(tmp_path):
    player_file = tmp_path / "topper.py"
    player_file.write_text(
        "class Topper:\n"
        "    avatar = 'hdyiihba/The_Merovingian_200x200_rqd12y.png'\n"
        "    def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):\n"
        "        return None\n"
    )
    result = _run(player_file, _base_lb(), tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    lb = yaml.safe_load((tmp_path / "leaderboard.yaml").read_text())
    assert lb["players"]["Topper"]["avatar"] == "hdyiihba/The_Merovingian_200x200_rqd12y.png"


def test_removes_avatar_when_attribute_removed(tmp_path):
    player_file = tmp_path / "topper.py"
    player_file.write_text(
        "class Topper:\n"
        "    def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):\n"
        "        return None\n"
    )
    lb = _base_lb()
    lb["players"]["Topper"]["avatar"] = "hdyiihba/The_Merovingian_200x200_rqd12y.png"
    result = _run(player_file, lb, tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    updated = yaml.safe_load((tmp_path / "leaderboard.yaml").read_text())
    assert "avatar" not in updated["players"]["Topper"]


def test_rejects_invalid_avatar(tmp_path):
    player_file = tmp_path / "topper.py"
    player_file.write_text(
        "class Topper:\n"
        "    avatar = 'not-a-valid-avatar'\n"
        "    def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):\n"
        "        return None\n"
    )
    result = _run(player_file, _base_lb(), tmp_path)
    assert result.returncode == 1
    assert "ERROR" in result.stdout + result.stderr


def test_display_name_still_updates(tmp_path):
    """Existing display_name sync behavior must survive the rename/extension."""
    player_file = tmp_path / "topper.py"
    player_file.write_text(
        "class Topper:\n"
        "    name = 'Topper the Great'\n"
        "    def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):\n"
        "        return None\n"
    )
    result = _run(player_file, _base_lb(), tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    lb = yaml.safe_load((tmp_path / "leaderboard.yaml").read_text())
    assert lb["players"]["Topper"]["display_name"] == "Topper the Great"


def test_player_not_in_leaderboard_warns(tmp_path):
    player_file = tmp_path / "unknown.py"
    player_file.write_text(
        "class Unknown:\n"
        "    def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):\n"
        "        return None\n"
    )
    result = _run(player_file, {"players": {}}, tmp_path)
    assert result.returncode == 0
    assert "WARNING" in result.stdout
