import json
import os
import subprocess
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).parent.parent


def run_game(args: list[str], leaderboard: dict, tmp_path: Path) -> dict:
    """Run `python -m game` with a temp leaderboard, return parsed results JSON."""
    lb_path = tmp_path / "leaderboard.yaml"
    lb_path.write_text(yaml.dump(leaderboard, default_flow_style=False, sort_keys=False))

    results_path = tmp_path / "results.json"
    cmd = [
        "uv",
        "run",
        "python",
        "-m",
        "game",
        *args,
        "--results-file",
        str(results_path),
    ]
    env = {**os.environ, "LEADERBOARD_PATH": str(lb_path)}
    result = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, env=env)
    assert result.returncode == 0, result.stderr

    if results_path.exists():
        return json.loads(results_path.read_text())
    return {}


def test_tier_prm_selects_only_prm_players(tmp_path):
    """--tier PRM runs only PRM players, not CH players."""
    lb = {
        "total_runs": 1,
        "pending_relegation": [],
        "players": {
            "Alice": {
                "display_name": "Alice",
                "github_username": "",
                "tier": "PRM",
                "date_added": "2026-01-01T00:00:00Z",
                "tier_since": "2026-01-01T00:00:00Z",
                "times_inactive": 0,
                "tier_stats": {"PRM": {"wins": 40, "games": 100, "win_pct": 40.0}},
            },
            "Diego": {
                "display_name": "Diego",
                "github_username": "",
                "tier": "PRM",
                "date_added": "2026-01-01T00:00:00Z",
                "tier_since": "2026-01-01T00:00:00Z",
                "times_inactive": 0,
                "tier_stats": {"PRM": {"wins": 30, "games": 100, "win_pct": 30.0}},
            },
            "Bruno": {
                "display_name": "Bruno",
                "github_username": "",
                "tier": "CH",
                "date_added": "2026-01-01T00:00:00Z",
                "tier_since": "2026-01-01T00:00:00Z",
                "times_inactive": 0,
                "tier_stats": {"CH": {"wins": 30, "games": 100, "win_pct": 30.0}},
            },
        },
    }
    results = run_game(["--tier", "PRM", "10", "4"], lb, tmp_path)
    assert "Alice" in results
    assert "Diego" in results
    assert "Bruno" not in results


def test_tier_l1_excludes_inactive_players(tmp_path):
    """--tier L1 runs only L1 players; inactive players are excluded."""
    lb = {
        "total_runs": 1,
        "players": {
            "Alice": {
                "display_name": "Alice",
                "github_username": "",
                "date_added": "2026-01-01T00:00:00Z",
                "tier": "L1",
                "tier_since": "2026-01-01T00:00:00Z",
                "times_inactive": 0,
                "tier_stats": {"L1": {"wins": 40, "games": 100, "win_pct": 40.0}},
            },
            "Bruno": {
                "display_name": "Bruno",
                "github_username": "",
                "date_added": "2026-01-01T00:00:00Z",
                "tier": "inactive",
                "tier_since": "2026-01-01T00:00:00Z",
                "times_inactive": 2,
                "tier_stats": {"L1": {"wins": 30, "games": 100, "win_pct": 30.0}},
            },
            "Cleo": {
                "display_name": "Cleo",
                "github_username": "",
                "date_added": "2026-01-01T00:00:00Z",
                "tier": "L1",
                "tier_since": "2026-01-01T00:00:00Z",
                "times_inactive": 0,
                "tier_stats": {},
            },
        },
    }
    results = run_game(["--tier", "L1", "10", "4"], lb, tmp_path)
    # L1 run: Alice and Cleo compete; Bruno (inactive) is excluded
    assert set(results.keys()) == {"Alice", "Cleo"}, (
        f"Expected only L1 players, got: {set(results.keys())}"
    )
    assert "Bruno" not in results


def test_results_file_written(tmp_path):
    """--results-file writes a JSON dict of {player: wins}."""
    lb = {
        "total_runs": 1,
        "pending_relegation": [],
        "players": {
            "Alice": {
                "display_name": "Alice",
                "github_username": "",
                "tier": "PRM",
                "date_added": "2026-01-01T00:00:00Z",
                "tier_since": "2026-01-01T00:00:00Z",
                "times_inactive": 0,
                "tier_stats": {"PRM": {"wins": 40, "games": 100, "win_pct": 40.0}},
            },
            "Bruno": {
                "display_name": "Bruno",
                "github_username": "",
                "tier": "PRM",
                "date_added": "2026-01-01T00:00:00Z",
                "tier_since": "2026-01-01T00:00:00Z",
                "times_inactive": 0,
                "tier_stats": {"PRM": {"wins": 30, "games": 100, "win_pct": 30.0}},
            },
        },
    }
    results = run_game(["--tier", "PRM", "5", "4"], lb, tmp_path)
    total = sum(results.values())
    assert total == 5  # exactly N_GAMES wins distributed


def test_no_leaderboard_update_written(tmp_path):
    """Running the game must NOT modify leaderboard.yaml."""
    lb = {
        "total_runs": 1,
        "pending_relegation": [],
        "players": {
            "Alice": {
                "display_name": "Alice",
                "github_username": "",
                "tier": "PRM",
                "date_added": "2026-01-01T00:00:00Z",
                "tier_since": "2026-01-01T00:00:00Z",
                "times_inactive": 0,
                "tier_stats": {"PRM": {"wins": 40, "games": 100, "win_pct": 40.0}},
            },
            "Bruno": {
                "display_name": "Bruno",
                "github_username": "",
                "tier": "PRM",
                "date_added": "2026-01-01T00:00:00Z",
                "tier_since": "2026-01-01T00:00:00Z",
                "times_inactive": 0,
                "tier_stats": {"PRM": {"wins": 30, "games": 100, "win_pct": 30.0}},
            },
        },
    }
    lb_path = tmp_path / "leaderboard.yaml"
    lb_path.write_text(yaml.dump(lb, default_flow_style=False, sort_keys=False))
    original_content = lb_path.read_text()

    results_path = tmp_path / "results.json"
    env = {**os.environ, "LEADERBOARD_PATH": str(lb_path)}
    subprocess.run(
        [
            "uv",
            "run",
            "python",
            "-m",
            "game",
            "--tier",
            "PRM",
            "--results-file",
            str(results_path),
            "5",
            "4",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        check=True,
        env=env,
    )
    assert lb_path.read_text() == original_content


def test_class_name_used_as_leaderboard_key(tmp_path):
    """Game results dict uses class name (type(p).__name__), not p.name attribute."""
    lb = {
        "total_runs": 1,
        "players": {
            "Alice": {
                "display_name": "Alice",
                "github_username": "",
                "tier": "PRM",
                "date_added": "2026-01-01T00:00:00Z",
                "tier_since": "2026-01-01T00:00:00Z",
                "times_inactive": 0,
                "tier_stats": {"PRM": {"wins": 40, "games": 100, "win_pct": 40.0}},
            },
            "Bruno": {
                "display_name": "Bruno",
                "github_username": "",
                "tier": "PRM",
                "date_added": "2026-01-01T00:00:00Z",
                "tier_since": "2026-01-01T00:00:00Z",
                "times_inactive": 0,
                "tier_stats": {"PRM": {"wins": 30, "games": 100, "win_pct": 30.0}},
            },
        },
    }
    results = run_game(["5", "4"], lb, tmp_path)
    assert set(results.keys()) == {"Alice", "Bruno"}
