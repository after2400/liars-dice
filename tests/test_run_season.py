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

    # Must contain final standings and game results sections
    assert "## Final Standings" in summary, "Missing Final Standings section"
    assert "## Game Results" in summary, "Missing Game Results section"

    # PRM appears as subsection in standings and as a collapsed game results block
    assert "### Premier" in summary, "Missing Premier subsection in standings"
    assert "<summary>Premier" in summary, "Missing Premier game results details block"

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


# ---------------------------------------------------------------------------
# Task 3: duplicate-name disambiguation in summary + README rendering
# ---------------------------------------------------------------------------


def _load_run_season(module_name="run_season"):
    """Import run_season.py as a module (main() is guarded, so this is side-effect free)."""
    # Distinct module_name lets a test load an isolated second copy of the
    # script (same name would collide in sys.modules and share monkeypatches).
    import importlib.util

    spec = importlib.util.spec_from_file_location(module_name, SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_summary_disambiguates_duplicate_names(tmp_path):
    rs = _load_run_season()
    lb_path = tmp_path / "lb.yaml"
    summary = tmp_path / "summary.md"
    data = {
        "total_runs": 1,
        "players": {
            "TopperA": {
                "display_name": "Topper",
                "github_username": "alice",
                "tier": "PRM",
                "tier_stats": {"PRM": {"wins": 5, "games": 10, "win_pct": 50.0}},
            },
            "TopperB": {
                "display_name": "Topper",
                "github_username": "bob",
                "tier": "PRM",
                "tier_stats": {"PRM": {"wins": 3, "games": 10, "win_pct": 30.0}},
            },
            "Solo": {
                "display_name": "Solo",
                "github_username": "",
                "tier": "PRM",
                "tier_stats": {"PRM": {"wins": 1, "games": 10, "win_pct": 10.0}},
            },
        },
    }
    lb_path.write_text(yaml.dump(data))

    rs._write_summary(str(summary), {}, [], 10, str(lb_path))
    text = summary.read_text()

    assert "Topper (alice)" in text
    assert "Topper (bob)" in text
    assert "Solo (" not in text  # unique name stays bare


def test_readme_disambiguates_duplicate_names(tmp_path):
    rs = _load_run_season()
    lb_path = tmp_path / "lb.yaml"
    readme = tmp_path / "README.md"
    readme.write_text(
        "intro\n"
        "<!-- prettier-ignore-start -->\n"
        "<!-- leaderboard-start -->\n"
        "OLD\n"
        "<!-- leaderboard-end -->\n"
        "<!-- prettier-ignore-end -->\n"
        "footer\n"
    )
    data = {
        "players": {
            "TopperA": {
                "display_name": "Topper",
                "github_username": "alice",
                "tier": "PRM",
                "tier_stats": {"PRM": {"win_pct": 50.0}},
            },
            "TopperB": {
                "display_name": "Topper",
                "github_username": "bob",
                "tier": "PRM",
                "tier_stats": {"PRM": {"win_pct": 30.0}},
            },
        },
    }
    lb_path.write_text(yaml.dump(data))

    rs._update_readme(str(readme), str(lb_path))
    text = readme.read_text()

    assert "Topper (alice)" in text
    assert "Topper (bob)" in text


# ---------------------------------------------------------------------------
# Test 5: standings Games column shows total games across all tiers
# ---------------------------------------------------------------------------


def test_standings_games_column_shows_total_games_not_current_tier():
    """The 'Games' column (totals group) must show total games across all tiers,
    not just the current tier's games."""
    mod = _load_run_season()
    # Eva: 3000 games in CH + 2000 in PRM = 5000 total; 1057+433 = 1490 total wins.
    player = {
        "tier_stats": {
            "CH": {"wins": 1057, "games": 3000, "win_pct": 35.2},
            "PRM": {"wins": 433, "games": 2000, "win_pct": 21.6},
        }
    }
    rows = mod._standings_table([("Eva", player)], "PRM", {"Eva": "Eva"})
    data_row = rows[2]  # rows[0]=header, rows[1]=separator, rows[2]=first data row
    # Totals group must be internally consistent: Total Wins=1490, Games=5000, Win% Total=29.8.
    assert data_row.endswith("| 29.8 | 1490 | 5000 |")
    # Must NOT show the current-tier (PRM) games of 2000 in the totals Games column.
    assert "| 1490 | 2000 |" not in data_row


# ---------------------------------------------------------------------------
# _quarter_leaderboard_table
# ---------------------------------------------------------------------------


def test_quarter_leaderboard_sort_prm_first():
    """Players are sorted PRM W% desc → CH W% desc → L1 W% desc."""
    mod = _load_run_season()
    players = {
        "Alpha": {
            "tier": "CH",
            "display_name": "Alpha",
            "tier_stats": {"CH": {"wins": 200, "games": 1000, "win_pct": 20.0}},
        },
        "Beta": {
            "tier": "PRM",
            "display_name": "Beta",
            "tier_stats": {"PRM": {"wins": 150, "games": 1000, "win_pct": 15.0}},
        },
        "Gamma": {
            "tier": "PRM",
            "display_name": "Gamma",
            "tier_stats": {"PRM": {"wins": 180, "games": 1000, "win_pct": 18.0}},
        },
    }
    rows = mod._quarter_leaderboard_table(players, {n: n for n in players})
    names = [r.split("|")[1].strip() for r in rows[2:]]
    assert names == ["Gamma", "Beta", "Alpha"]


def test_quarter_leaderboard_ch_tiebreak():
    """When PRM W% is equal, CH W% breaks the tie."""
    mod = _load_run_season()
    players = {
        "A": {
            "tier": "PRM",
            "display_name": "A",
            "tier_stats": {
                "PRM": {"wins": 150, "games": 1000, "win_pct": 15.0},
                "CH": {"wins": 200, "games": 1000, "win_pct": 20.0},
            },
        },
        "B": {
            "tier": "PRM",
            "display_name": "B",
            "tier_stats": {
                "PRM": {"wins": 150, "games": 1000, "win_pct": 15.0},
                "CH": {"wins": 100, "games": 1000, "win_pct": 10.0},
            },
        },
    }
    rows = mod._quarter_leaderboard_table(players, {"A": "A", "B": "B"})
    names = [r.split("|")[1].strip() for r in rows[2:]]
    assert names == ["A", "B"]


def test_quarter_leaderboard_no_stats_sorts_last():
    """Players with no tier_stats sort below players who have any stats."""
    mod = _load_run_season()
    players = {
        "HasStats": {
            "tier": "L1",
            "display_name": "HasStats",
            "tier_stats": {"L1": {"wins": 100, "games": 1000, "win_pct": 10.0}},
        },
        "NoStats": {
            "tier": "L1",
            "display_name": "NoStats",
            "tier_stats": {},
        },
    }
    rows = mod._quarter_leaderboard_table(players, {n: n for n in players})
    names = [r.split("|")[1].strip() for r in rows[2:]]
    assert names == ["HasStats", "NoStats"]


def test_quarter_leaderboard_dash_for_missing_tier():
    """Tiers the player has never played in show '—'."""
    mod = _load_run_season()
    players = {
        "OnlyL1": {
            "tier": "L1",
            "display_name": "OnlyL1",
            "tier_stats": {"L1": {"wins": 100, "games": 1000, "win_pct": 10.0}},
        },
    }
    rows = mod._quarter_leaderboard_table(players, {"OnlyL1": "OnlyL1"})
    data_row = rows[2]
    # PRM and CH should show "—", L1 should show 10.0
    assert "| — | — | 10.0 |" in data_row


def test_quarter_leaderboard_total_win_pct_across_tiers():
    """Total W% and Games aggregate all tiers, not just the current one."""
    mod = _load_run_season()
    players = {
        "Multi": {
            "tier": "PRM",
            "display_name": "Multi",
            "tier_stats": {
                "PRM": {"wins": 200, "games": 1000, "win_pct": 20.0},
                "CH": {"wins": 300, "games": 2000, "win_pct": 15.0},
                "L1": {"wins": 500, "games": 4000, "win_pct": 12.5},
            },
        },
    }
    rows = mod._quarter_leaderboard_table(players, {"Multi": "Multi"})
    data_row = rows[2]
    # total wins = 1000, total games = 7000, total W% = 14.3
    assert data_row.endswith("| 14.3 | 7000 |")


def test_update_readme_includes_quarter_leaderboard(tmp_path):
    """_update_readme must emit a Quarter Leaderboard section."""
    rs = _load_run_season()
    lb_path = tmp_path / "lb.yaml"
    readme = tmp_path / "README.md"
    readme.write_text(
        "intro\n"
        "<!-- prettier-ignore-start -->\n"
        "<!-- leaderboard-start -->\n"
        "OLD\n"
        "<!-- leaderboard-end -->\n"
        "<!-- prettier-ignore-end -->\n"
        "footer\n"
    )
    data = {
        "players": {
            "Eva": {
                "display_name": "Eva",
                "github_username": "",
                "tier": "PRM",
                "tier_stats": {"PRM": {"wins": 200, "games": 1000, "win_pct": 20.0}},
            },
        },
    }
    lb_path.write_text(yaml.dump(data))
    rs._update_readme(str(readme), str(lb_path))
    text = readme.read_text()
    assert "### Quarter Leaderboard" in text
    assert "PRM W%" in text
    assert "CH W%" in text
    assert "L1 W%" in text


# ---------------------------------------------------------------------------
# Task 3: end-to-end run_season with settlement
# ---------------------------------------------------------------------------


def _player(name, tier):
    return {
        "display_name": name,
        "github_username": "",
        "date_added": "2026-01-01T00:00:00Z",
        "tier": tier,
        "tier_since": "2026-01-01T00:00:00Z",
        "times_inactive": 0,
        "tier_stats": {},
    }


def test_run_season_rebalances_in_one_run(tmp_path, monkeypatch):
    """Full bottom-up promotion + top-down settlement produces a balanced ladder."""
    run_season_mod = _load_run_season("run_season_e2e")

    players = {
        "Diego": _player("Diego", "PRM"),
        "Eva": _player("Eva", "PRM"),
        "Sloane": _player("Sloane", "PRM"),
        "Zara": _player("Zara", "PRM"),
        "Alice": _player("Alice", "CH"),
        "Bruno": _player("Bruno", "CH"),
        "Finn": _player("Finn", "CH"),
        "Remy": _player("Remy", "CH"),
        "Cleo": _player("Cleo", "L1"),
        "Pyro": _player("Pyro", "L1"),
        "Topper": _player("Topper", "L1"),
    }
    lb_path = str(tmp_path / "leaderboard.yaml")
    (tmp_path / "leaderboard.yaml").write_text(
        yaml.dump({"total_runs": 0, "last_updated": "x", "players": players})
    )

    # Canned per-tier win counts. Cleo wins L1 (promoted), flops in CH;
    # Remy wins CH (promoted), flops in PRM.
    canned = {
        "L1": {"Cleo": 471, "Topper": 444, "Pyro": 85},
        "CH": {"Remy": 337, "Finn": 312, "Alice": 194, "Bruno": 153, "Cleo": 4},
        "PRM": {"Sloane": 240, "Eva": 235, "Zara": 217, "Diego": 202, "Remy": 106},
    }
    monkeypatch.setattr(run_season_mod, "_run_tier", lambda tier, n, t, p: canned.get(tier, {}))

    run_season_mod.run_season(
        n_games=1000,
        top_n=4,
        lb_path=lb_path,
        summary_file=str(tmp_path / "summary.md"),
        readme_path=str(tmp_path / "README.md"),  # no markers → README update is a no-op
    )

    result = yaml.safe_load(Path(lb_path).read_text())["players"]

    def by_tier(t):
        return {n for n, p in result.items() if p["tier"] == t}

    assert by_tier("PRM") == {"Diego", "Eva", "Sloane", "Zara"}
    assert by_tier("CH") == {"Alice", "Bruno", "Finn", "Remy"}  # Remy parachuted back
    assert by_tier("L1") == {"Pyro", "Topper", "Cleo"}  # Cleo bounced back


def test_run_season_reads_issue_number_from_leaderboard(tmp_path, monkeypatch):
    """run_season.py should read current_season_issue from leaderboard.yaml."""
    run_season_mod = _load_run_season("run_season_issue_test")

    captured = {}

    def fake_post(issue_number, summary_file):
        captured["issue"] = issue_number

    monkeypatch.setattr(run_season_mod, "_post_season_summary", fake_post)

    lb_path = tmp_path / "leaderboard.yaml"
    lb = {
        "total_runs": 0,
        "last_updated": "2026-01-01T00:00:00Z",
        "current_season_issue": 99,
        "players": {},
    }
    lb_path.write_text(yaml.dump(lb))

    run_season_mod._post_season_from_lb(str(lb_path), str(tmp_path / "summary.md"))
    assert captured["issue"] == 99


def test_dry_run_skips_post_season_summary(monkeypatch, capsys):
    monkeypatch.setenv("DRY_RUN", "1")
    rs = _load_run_season("run_season_dry")
    rs._post_season_summary(77, "/tmp/summary.md")
    out = capsys.readouterr().out
    assert "[dry-run]" in out


def test_dry_run_skips_readme_update(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("DRY_RUN", "1")
    rs = _load_run_season("run_season_dry_readme")
    readme = tmp_path / "README.md"
    readme.write_text("original content")
    rs._update_readme(str(readme), str(tmp_path / "lb.yaml"))
    assert readme.read_text() == "original content", "dry-run must not write README"
