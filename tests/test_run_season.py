"""Integration tests for .github/scripts/run_season.py.

These tests run the script as a subprocess (since it orchestrates subprocess calls
to `python -m game`) using real player files from players/.
"""

import os
import subprocess
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).parent.parent
SCRIPT = REPO_ROOT / ".github" / "scripts" / "run_season.py"


def _make_leaderboard(players: dict) -> dict:
    """Build a minimal leaderboard dict from a mapping of class_name → tier."""
    now = "2026-01-01T00:00:00Z"
    return {
        "total_runs": 0,
        "last_updated": now,
        "players": {
            name: {
                "display_name": name,
                "github_username": "",
                "date_added": now,
                "tier": tier,
                "tier_since": now,
                "times_inactive": 0,
                "tier_stats": {},
            }
            for name, tier in players.items()
        },
    }


def _run_season(lb_path: Path, summary_path: Path, n_games: int = 5) -> subprocess.CompletedProcess:
    """Run run_season.py with the given leaderboard and summary paths."""
    readme_path = lb_path.parent / "README.md"
    readme_path.write_text("<!-- leaderboard-start -->\n<!-- leaderboard-end -->\n")
    env = {
        **os.environ,
        "LEADERBOARD_PATH": str(lb_path),
        "SUMMARY_FILE": str(summary_path),
        "README_PATH": str(readme_path),
        "N_GAMES": str(n_games),
        "TOP_N": "4",
    }
    result = subprocess.run(
        ["uv", "run", "python", str(SCRIPT)],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(REPO_ROOT),
    )
    return result


# ---------------------------------------------------------------------------
# Test 1: Tier with fewer than 2 players is skipped
# ---------------------------------------------------------------------------


def test_skips_tier_with_fewer_than_2_players(tmp_path):
    """A tier with only 1 player must be skipped — no crash, leaderboard unchanged."""
    lb_path = tmp_path / "leaderboard.yaml"
    summary_path = tmp_path / "summary.md"

    # Only 1 PRM player — PRM should be skipped
    lb = _make_leaderboard({"Alice": "PRM"})
    lb_path.write_text(yaml.dump(lb, default_flow_style=False, sort_keys=False))

    result = _run_season(lb_path, summary_path, n_games=5)

    assert result.returncode == 0, f"Script failed:\n{result.stderr}"

    # Leaderboard stats should NOT have been updated (games == 0 for PRM)
    updated = yaml.safe_load(lb_path.read_text())
    alice_stats = updated["players"]["Alice"].get("tier_stats", {}).get("PRM", {})
    assert alice_stats.get("games", 0) == 0, "PRM stats should not be updated for a skipped tier"

    # Summary should mention skipped tier
    assert summary_path.exists(), "Summary file should be written even when tiers are skipped"
    summary = summary_path.read_text()
    assert "PRM" in summary
    # Skipped note should appear somewhere
    assert "skip" in summary.lower() or "< 2" in summary or "Skipped" in summary


# ---------------------------------------------------------------------------
# Test 2: Active tier runs and updates leaderboard stats
# ---------------------------------------------------------------------------


def test_runs_active_tier_and_updates_leaderboard(tmp_path):
    """With 2 PRM players, run_season should play games and increment stats."""
    lb_path = tmp_path / "leaderboard.yaml"
    summary_path = tmp_path / "summary.md"

    # Alice and Bruno are real player classes in players/
    lb = _make_leaderboard({"Alice": "PRM", "Bruno": "PRM"})
    lb_path.write_text(yaml.dump(lb, default_flow_style=False, sort_keys=False))

    result = _run_season(lb_path, summary_path, n_games=10)

    assert result.returncode == 0, (
        f"Script failed:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"
    )

    updated = yaml.safe_load(lb_path.read_text())

    # Total games across both players must equal n_games (each player gets n_games recorded)
    alice_games = updated["players"]["Alice"].get("tier_stats", {}).get("PRM", {}).get("games", 0)
    bruno_games = updated["players"]["Bruno"].get("tier_stats", {}).get("PRM", {}).get("games", 0)

    # Both players competed in 10 games each
    assert alice_games == 10, f"Alice should have 10 games recorded, got {alice_games}"
    assert bruno_games == 10, f"Bruno should have 10 games recorded, got {bruno_games}"


# ---------------------------------------------------------------------------
# Test 3: Summary file is written with expected content
# ---------------------------------------------------------------------------


def test_writes_summary_file(tmp_path):
    """run_season should create a markdown summary with tier sections and a date."""
    lb_path = tmp_path / "leaderboard.yaml"
    summary_path = tmp_path / "summary.md"

    lb = _make_leaderboard({"Alice": "PRM", "Bruno": "PRM"})
    lb_path.write_text(yaml.dump(lb, default_flow_style=False, sort_keys=False))

    result = _run_season(lb_path, summary_path, n_games=5)

    assert result.returncode == 0, (
        f"Script failed:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"
    )

    assert summary_path.exists(), "SUMMARY_FILE was not created"
    summary = summary_path.read_text()

    # Must have a top-level heading
    assert summary.startswith("# Season Summary"), f"Unexpected start:\n{summary[:200]}"

    # Must contain PRM section
    assert "## PRM" in summary, "Missing PRM section in summary"

    # Must contain a markdown table
    assert "| Player" in summary or "|Player" in summary, "No table header found"

    # Should mention player names
    assert "Alice" in summary
    assert "Bruno" in summary


# ---------------------------------------------------------------------------
# Test 4: Inactive tier runs separately when there are ≥2 inactive players
# ---------------------------------------------------------------------------


def test_runs_inactive_tier_separately(tmp_path):
    """Inactive players run their own separate game before L1."""
    lb_path = tmp_path / "leaderboard.yaml"
    summary_path = tmp_path / "summary.md"

    # 2 inactive players (Alice, Bruno are real player classes)
    lb = _make_leaderboard({"Alice": "inactive", "Bruno": "inactive"})
    lb_path.write_text(yaml.dump(lb, default_flow_style=False, sort_keys=False))

    result = _run_season(lb_path, summary_path, n_games=5)

    assert result.returncode == 0, (
        f"Script failed:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"
    )

    updated = yaml.safe_load(lb_path.read_text())

    # At least one of Alice/Bruno should have inactive tier_stats updated
    alice_stats = updated["players"]["Alice"].get("tier_stats", {}).get("inactive", {})
    bruno_stats = updated["players"]["Bruno"].get("tier_stats", {}).get("inactive", {})
    assert alice_stats.get("games", 0) == 5 or bruno_stats.get("games", 0) == 5, (
        "Expected inactive tier stats to be recorded after running the tier"
    )
    # Both should have games recorded
    assert alice_stats.get("games", 0) == 5, f"Alice should have 5 games, got {alice_stats}"
    assert bruno_stats.get("games", 0) == 5, f"Bruno should have 5 games, got {bruno_stats}"
