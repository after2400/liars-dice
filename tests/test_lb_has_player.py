import os
import subprocess
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).parent.parent
SCRIPT = REPO_ROOT / ".github/scripts/lb_has_player.py"


def _run(stem: str, lb: dict, tmp_path: Path) -> str:
    lb_path = tmp_path / "leaderboard.yaml"
    lb_path.write_text(yaml.dump(lb, default_flow_style=False, sort_keys=False))
    result = subprocess.run(
        ["uv", "run", "python", str(SCRIPT), stem],
        cwd=str(tmp_path),
        env={**os.environ},
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def test_present_exact(tmp_path):
    lb = {"players": {"Topper": {"github_username": "alice"}}}
    assert _run("Topper", lb, tmp_path) == "true"


def test_present_case_insensitive(tmp_path):
    lb = {"players": {"Topper": {"github_username": "alice"}}}
    assert _run("topper", lb, tmp_path) == "true"


def test_absent(tmp_path):
    lb = {"players": {"Topper": {"github_username": "alice"}}}
    assert _run("pyro", lb, tmp_path) == "false"


def test_no_players_key(tmp_path):
    assert _run("topper", {}, tmp_path) == "false"


def test_missing_file(tmp_path):
    result = subprocess.run(
        ["uv", "run", "python", str(SCRIPT), "topper"],
        cwd=str(tmp_path),  # no leaderboard.yaml here
        env={**os.environ},
        capture_output=True,
        text=True,
    )
    assert result.stdout.strip() == "false"
    assert result.returncode == 0
