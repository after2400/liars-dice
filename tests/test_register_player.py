import os
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).parent.parent


def run_register(
    player_file: str, lb: dict, tmp_path: Path, github_username: str = "testuser"
) -> tuple[int, str]:
    """Run register_player.py in a temp dir. Returns (returncode, stdout+stderr)."""
    import subprocess

    lb_path = tmp_path / "leaderboard.yaml"
    lb_path.write_text(yaml.dump(lb, default_flow_style=False, sort_keys=False))

    env = {
        **os.environ,
        "PLAYER_FILE": str(player_file),
        "GITHUB_USERNAME": github_username,
        "LEADERBOARD_PATH": str(lb_path),
    }
    result = subprocess.run(
        ["uv", "run", "python", str(REPO_ROOT / ".github/scripts/register_player.py")],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout + result.stderr


def test_register_new_player_enters_l1_when_l1_has_player(tmp_path):
    lb = {
        "total_runs": 0,
        "players": {
            "Alice": {
                "display_name": "Alice",
                "github_username": "",
                "tier": "L1",
                "tier_since": "2026-01-01T00:00:00Z",
                "date_added": "2026-01-01T00:00:00Z",
                "times_inactive": 0,
                "tier_stats": {},
            },
        },
    }
    player_file = REPO_ROOT / "players" / "bruno.py"
    rc, out = run_register(player_file, lb, tmp_path)
    assert rc == 0, out
    lb_result = yaml.safe_load((tmp_path / "leaderboard.yaml").read_text())
    assert lb_result["players"]["Bruno"]["tier"] == "L1"


def test_register_new_player_enters_ch_when_all_tiers_empty(tmp_path):
    lb = {"total_runs": 0, "players": {}}
    player_file = REPO_ROOT / "players" / "alice.py"
    rc, out = run_register(player_file, lb, tmp_path)
    assert rc == 0, out
    lb_result = yaml.safe_load((tmp_path / "leaderboard.yaml").read_text())
    assert lb_result["players"]["Alice"]["tier"] == "CH"


def test_register_stores_github_username(tmp_path):
    lb = {"total_runs": 0, "players": {}}
    player_file = REPO_ROOT / "players" / "alice.py"
    rc, out = run_register(player_file, lb, tmp_path, github_username="after2400")
    assert rc == 0, out
    lb_result = yaml.safe_load((tmp_path / "leaderboard.yaml").read_text())
    assert lb_result["players"]["Alice"]["github_username"] == "after2400"


def test_register_exits_0_if_already_registered(tmp_path):
    lb = {
        "total_runs": 0,
        "players": {
            "Alice": {
                "display_name": "Alice",
                "github_username": "someone",
                "tier": "PRM",
                "tier_since": "2026-01-01T00:00:00Z",
                "date_added": "2026-01-01T00:00:00Z",
                "times_inactive": 0,
                "tier_stats": {},
            },
        },
    }
    player_file = REPO_ROOT / "players" / "alice.py"
    rc, out = run_register(player_file, lb, tmp_path)
    assert rc == 0
    # Leaderboard unchanged
    lb_result = yaml.safe_load((tmp_path / "leaderboard.yaml").read_text())
    assert lb_result["players"]["Alice"]["github_username"] == "someone"


def test_register_enters_l1_when_l1_has_players_at_capacity(tmp_path):
    # L1 has players (even over capacity) → new player still enters L1; season run handles overflow
    lb = {
        "total_runs": 0,
        "players": {
            "P1": {
                "display_name": "P1",
                "github_username": "",
                "tier": "L1",
                "tier_since": "2026-01-01T00:00:00Z",
                "date_added": "2026-01-01T00:00:00Z",
                "times_inactive": 0,
                "tier_stats": {},
            },
            "P2": {
                "display_name": "P2",
                "github_username": "",
                "tier": "L1",
                "tier_since": "2026-01-01T00:00:00Z",
                "date_added": "2026-01-01T00:00:00Z",
                "times_inactive": 0,
                "tier_stats": {},
            },
            "P3": {
                "display_name": "P3",
                "github_username": "",
                "tier": "L1",
                "tier_since": "2026-01-01T00:00:00Z",
                "date_added": "2026-01-01T00:00:00Z",
                "times_inactive": 0,
                "tier_stats": {},
            },
            "P4": {
                "display_name": "P4",
                "github_username": "",
                "tier": "L1",
                "tier_since": "2026-01-01T00:00:00Z",
                "date_added": "2026-01-01T00:00:00Z",
                "times_inactive": 0,
                "tier_stats": {},
            },
            "Alice": {
                "display_name": "Alice",
                "github_username": "",
                "tier": "CH",
                "tier_since": "2026-01-01T00:00:00Z",
                "date_added": "2026-01-01T00:00:00Z",
                "times_inactive": 0,
                "tier_stats": {},
            },
        },
    }
    player_file = REPO_ROOT / "players" / "bruno.py"
    rc, out = run_register(player_file, lb, tmp_path)
    assert rc == 0, out
    lb_result = yaml.safe_load((tmp_path / "leaderboard.yaml").read_text())
    assert lb_result["players"]["Bruno"]["tier"] == "L1"


def test_register_enters_ch_when_l1_empty_and_ch_at_capacity(tmp_path):
    # L1 is empty (not active) and CH is over capacity → new player still enters CH; season run handles overflow
    lb = {
        "total_runs": 0,
        "players": {
            "Alice": {
                "display_name": "Alice",
                "github_username": "",
                "tier": "CH",
                "tier_since": "2026-01-01T00:00:00Z",
                "date_added": "2026-01-01T00:00:00Z",
                "times_inactive": 0,
                "tier_stats": {},
            },
            "Cleo": {
                "display_name": "Cleo",
                "github_username": "",
                "tier": "CH",
                "tier_since": "2026-01-01T00:00:00Z",
                "date_added": "2026-01-01T00:00:00Z",
                "times_inactive": 0,
                "tier_stats": {},
            },
            "Diego": {
                "display_name": "Diego",
                "github_username": "",
                "tier": "CH",
                "tier_since": "2026-01-01T00:00:00Z",
                "date_added": "2026-01-01T00:00:00Z",
                "times_inactive": 0,
                "tier_stats": {},
            },
            "Finn": {
                "display_name": "Finn",
                "github_username": "",
                "tier": "CH",
                "tier_since": "2026-01-01T00:00:00Z",
                "date_added": "2026-01-01T00:00:00Z",
                "times_inactive": 0,
                "tier_stats": {},
            },
        },
    }
    player_file = REPO_ROOT / "players" / "bruno.py"
    rc, out = run_register(player_file, lb, tmp_path)
    assert rc == 0, out
    lb_result = yaml.safe_load((tmp_path / "leaderboard.yaml").read_text())
    assert lb_result["players"]["Bruno"]["tier"] == "CH"


def test_register_enters_ch_when_l1_empty(tmp_path):
    # L1 has 0 players (not active) → skip L1, CH has 1 player → enter CH
    lb = {
        "total_runs": 0,
        "players": {
            "Alice": {
                "display_name": "Alice",
                "github_username": "",
                "tier": "CH",
                "tier_since": "2026-01-01T00:00:00Z",
                "date_added": "2026-01-01T00:00:00Z",
                "times_inactive": 0,
                "tier_stats": {},
            },
        },
    }
    player_file = REPO_ROOT / "players" / "bruno.py"
    rc, out = run_register(
        player_file,
        lb,
        tmp_path,
    )
    assert rc == 0, out
    lb_result = yaml.safe_load((tmp_path / "leaderboard.yaml").read_text())
    assert lb_result["players"]["Bruno"]["tier"] == "CH"


def test_stdout_contains_entry_tier(tmp_path):
    lb = {"total_runs": 0, "players": {}}
    player_file = REPO_ROOT / "players" / "alice.py"
    rc, out = run_register(player_file, lb, tmp_path)
    assert rc == 0, out
    assert "entry_tier=CH" in out


def test_stdout_entry_tier_when_already_registered(tmp_path):
    lb = {
        "total_runs": 0,
        "players": {
            "Alice": {
                "display_name": "Alice",
                "github_username": "someone",
                "tier": "CH",
                "tier_since": "2026-01-01T00:00:00Z",
                "date_added": "2026-01-01T00:00:00Z",
                "times_inactive": 0,
                "tier_stats": {},
            },
        },
    }
    player_file = REPO_ROOT / "players" / "alice.py"
    rc, out = run_register(player_file, lb, tmp_path)
    assert rc == 0, out
    assert "entry_tier=CH" in out


def test_register_rejects_name_too_long(tmp_path):
    player_py = tmp_path / "toolong.py"
    # A 26-char name, one over the 25-char limit.
    player_py.write_text("class Toolong:\n    name = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'\n")
    lb = {"total_runs": 0, "players": {}}
    rc, out = run_register(
        str(player_py),
        lb,
        tmp_path,
    )
    assert rc == 1, out
    assert "ERROR" in out


def test_register_rejects_name_with_parens(tmp_path):
    player_py = tmp_path / "withparens.py"
    player_py.write_text("class Withparens:\n    name = 'Bad (name)'\n")
    lb = {"total_runs": 0, "players": {}}
    rc, out = run_register(
        str(player_py),
        lb,
        tmp_path,
    )
    assert rc == 1, out
    assert "ERROR" in out
