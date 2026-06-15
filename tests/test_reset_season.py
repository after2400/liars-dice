"""Tests for .github/scripts/reset_season.py utility functions."""

import importlib.util
from datetime import date
from pathlib import Path

import yaml

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


# --- zero_stats ---


def _make_lb(players: dict, tournament_state=None) -> dict:
    lb = {
        "total_runs": 5,
        "last_updated": "2026-01-01T00:00:00Z",
        "current_season_issue": 10,
        "players": players,
    }
    if tournament_state:
        lb["tournament_state"] = tournament_state
    return lb


def _player(tier, wins=100, games=500):
    return {
        "display_name": "X",
        "github_username": "",
        "date_added": "2026-01-01T00:00:00Z",
        "tier": tier,
        "tier_since": "2026-01-01T00:00:00Z",
        "times_inactive": 0,
        "tier_stats": {
            tier: {
                "wins": wins,
                "games": games,
                "win_pct": round(wins / games * 100, 1) if games else 0.0,
            }
        },
    }


def test_zero_stats_clears_all_tier_stats(tmp_path):
    mod = _load()
    lb = _make_lb(
        {
            "Alice": _player("PRM"),
            "Bruno": _player("CH"),
        }
    )
    path = str(tmp_path / "lb.yaml")
    (tmp_path / "lb.yaml").write_text(yaml.dump(lb))

    mod.zero_stats(path, quarter="2026-Q3")

    result = yaml.safe_load(Path(path).read_text())
    assert result["players"]["Alice"]["tier_stats"] == {}
    assert result["players"]["Bruno"]["tier_stats"] == {}
    assert result["tournament_state"]["quarter"] == "2026-Q3"


def test_zero_stats_is_idempotent(tmp_path):
    """Calling zero_stats twice for the same quarter is a no-op on the second call."""
    mod = _load()
    lb = _make_lb({"Alice": _player("PRM")})
    path = str(tmp_path / "lb.yaml")
    (tmp_path / "lb.yaml").write_text(yaml.dump(lb))

    mod.zero_stats(path, quarter="2026-Q3")
    # Manually re-add stats to verify second call doesn't re-zero
    result = yaml.safe_load(Path(path).read_text())
    result["players"]["Alice"]["tier_stats"] = {"PRM": {"wins": 99, "games": 100, "win_pct": 99.0}}
    Path(path).write_text(yaml.dump(result))

    mod.zero_stats(path, quarter="2026-Q3")  # same quarter → skip

    result2 = yaml.safe_load(Path(path).read_text())
    # Stats were NOT re-zeroed (idempotent skip)
    assert result2["players"]["Alice"]["tier_stats"]["PRM"]["wins"] == 99


def test_run_pools_stores_results(tmp_path, monkeypatch):
    """run_pools() stores per-pool win dicts in tournament_state.pool_results."""
    mod = _load()

    canned = {"Alice": 450, "Bruno": 300, "Cleo": 250}
    monkeypatch.setattr(
        mod, "_run_pool", lambda pool, n_games, lb_path: {p: canned[p] for p in pool if p in canned}
    )

    lb = _make_lb(
        {"Alice": _player("PRM"), "Bruno": _player("CH"), "Cleo": _player("L1")},
        tournament_state={"quarter": "2026-Q3"},
    )
    path = str(tmp_path / "lb.yaml")
    (tmp_path / "lb.yaml").write_text(yaml.dump(lb))

    mod.run_pools(path, n_games=10)

    result = yaml.safe_load(Path(path).read_text())
    pool_results = result["tournament_state"]["pool_results"]
    assert len(pool_results) == 1  # 3 players → 1 pool (ceil(3/8)=1)
    wins = list(pool_results.values())[0]
    assert set(wins.keys()) == {"Alice", "Bruno", "Cleo"}


def test_run_pools_is_idempotent(tmp_path, monkeypatch):
    """run_pools() skips if pool_results already present."""
    mod = _load()
    called = []
    monkeypatch.setattr(mod, "_run_pool", lambda *a, **kw: called.append(1) or {})

    lb = _make_lb(
        {"Alice": _player("PRM"), "Bruno": _player("CH")},
        tournament_state={
            "quarter": "2026-Q3",
            "pool_results": {"pool_0": {"Alice": 5, "Bruno": 3}},
        },
    )
    path = str(tmp_path / "lb.yaml")
    (tmp_path / "lb.yaml").write_text(yaml.dump(lb))

    mod.run_pools(path, n_games=10)
    assert len(called) == 0  # _run_pool was never called


def test_assign_placements_fills_tiers_top_down(tmp_path):
    """Top win-count players go to PRM, next to CH, etc."""
    mod = _load()
    # 11 players: caps = {PRM:4, CH:4, L1:3, DED:0}
    names = [f"P{i}" for i in range(11)]
    players = {n: _player("L1", wins=0, games=0) for n in names}
    pool_results = {
        "pool_0": {n: 500 - i * 40 for i, n in enumerate(names[:6])},
        "pool_1": {n: 500 - i * 40 for i, n in enumerate(names[6:])},
    }
    lb = _make_lb(players, tournament_state={"quarter": "2026-Q3", "pool_results": pool_results})
    path = str(tmp_path / "lb.yaml")
    (tmp_path / "lb.yaml").write_text(yaml.dump(lb))

    mod.assign_placements(path, n_games=1000)

    result = yaml.safe_load(Path(path).read_text())["players"]
    tiers = {n: p["tier"] for n, p in result.items()}
    prm_players = [n for n, t in tiers.items() if t == "PRM"]
    ch_players = [n for n, t in tiers.items() if t == "CH"]
    l1_players = [n for n, t in tiers.items() if t == "L1"]
    assert len(prm_players) == 4
    assert len(ch_players) == 4
    assert len(l1_players) == 3


def test_assign_placements_top_scorer_in_prm(tmp_path):
    """The player with the most wins ends up in PRM."""
    mod = _load()
    players = {
        n: _player("CH", wins=0, games=0)
        for n in [
            "Alice",
            "Bruno",
            "Cleo",
            "Diego",
            "Eva",
            "Finn",
            "Remy",
            "Sloane",
            "Zara",
            "Pyro",
            "Topper",
        ]
    }
    # Alice dominates
    wins = {
        "Alice": 800,
        "Bruno": 600,
        "Cleo": 500,
        "Diego": 490,
        "Eva": 480,
        "Finn": 470,
        "Remy": 460,
        "Sloane": 450,
        "Zara": 440,
        "Pyro": 430,
        "Topper": 420,
    }
    pool_results = {"pool_0": wins}
    lb = _make_lb(players, tournament_state={"quarter": "2026-Q3", "pool_results": pool_results})
    path = str(tmp_path / "lb.yaml")
    (tmp_path / "lb.yaml").write_text(yaml.dump(lb))

    mod.assign_placements(path, n_games=1000)

    result = yaml.safe_load(Path(path).read_text())["players"]
    assert result["Alice"]["tier"] == "PRM"
    assert result["Topper"]["tier"] == "L1"


def test_create_season_issue_is_idempotent(tmp_path, monkeypatch):
    """create_season_issue() skips if tournament_state.issue_created is True."""
    mod = _load()
    called = []
    monkeypatch.setattr(mod, "_gh_create_issue", lambda *a, **kw: called.append(1) or 99)

    lb = _make_lb(
        {"Alice": _player("PRM")},
        tournament_state={"quarter": "2026-Q3", "issue_created": True},
    )
    path = str(tmp_path / "lb.yaml")
    (tmp_path / "lb.yaml").write_text(yaml.dump(lb))

    mod.create_season_issue(path, quarter="2026-Q3", summary_file=str(tmp_path / "s.md"))
    assert len(called) == 0  # skipped


def test_create_season_issue_writes_issue_number(tmp_path, monkeypatch):
    """create_season_issue() stores the new issue number in leaderboard.yaml."""
    mod = _load()
    monkeypatch.setenv("GH_REPO", "owner/repo")
    monkeypatch.setattr(mod, "_gh_create_issue", lambda title, repo: 42)
    monkeypatch.setattr(mod, "_gh_post_comment", lambda issue, body_file, repo: None)

    summary = tmp_path / "s.md"
    summary.write_text("# Tournament Summary\n")
    lb = _make_lb(
        {"Alice": _player("PRM")},
        tournament_state={"quarter": "2026-Q3"},
    )
    path = str(tmp_path / "lb.yaml")
    (tmp_path / "lb.yaml").write_text(yaml.dump(lb))

    mod.create_season_issue(path, quarter="2026-Q3", summary_file=str(summary))

    result = yaml.safe_load(Path(path).read_text())
    assert result["current_season_issue"] == 42
    assert result["tournament_state"]["issue_created"] is True


def test_write_tournament_summary_contains_tier_placements(tmp_path):
    """_write_tournament_summary writes tier placements and pool results."""
    mod = _load()
    players = {
        "Alice": _player("PRM"),
        "Bruno": _player("CH"),
        "Cleo": _player("L1"),
    }
    pool_results = {"pool_0": {"Alice": 500, "Bruno": 300, "Cleo": 200}}
    lb = _make_lb(players, tournament_state={"quarter": "2026-Q3", "pool_results": pool_results})
    path = str(tmp_path / "lb.yaml")
    (tmp_path / "lb.yaml").write_text(yaml.dump(lb))
    summary = str(tmp_path / "summary.md")

    mod._write_tournament_summary(summary, path, "2026-Q3")

    text = Path(summary).read_text()
    assert "# Tournament Summary — 2026-Q3" in text
    assert "Premier" in text  # PRM label
    assert "Alice" in text
    assert "## Pool Results" in text
    assert "500" in text  # Alice's wins


def test_today_reads_env_var(monkeypatch):
    monkeypatch.setenv("TODAY", "2026-07-07")
    mod = _load()
    assert mod._today() == date(2026, 7, 7)


def test_today_falls_back_to_real_date(monkeypatch):
    monkeypatch.delenv("TODAY", raising=False)
    mod = _load()
    expected = date.today()
    assert mod._today() == expected


def test_dry_run_skips_gh_create_issue(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("DRY_RUN", "1")
    import importlib.util
    import pathlib

    spec = importlib.util.spec_from_file_location(
        "reset_season_dry",
        pathlib.Path(__file__).parent.parent / ".github/scripts/reset_season.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    result = mod._gh_create_issue("Test Issue", "owner/repo")
    assert result == 0
    out = capsys.readouterr().out
    assert "[dry-run]" in out


def test_dry_run_skips_gh_post_comment(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("DRY_RUN", "1")
    import importlib.util
    import pathlib

    spec = importlib.util.spec_from_file_location(
        "reset_season_dry2",
        pathlib.Path(__file__).parent.parent / ".github/scripts/reset_season.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    body_file = tmp_path / "body.md"
    body_file.write_text("test body")
    mod._gh_post_comment(42, str(body_file), "owner/repo")
    out = capsys.readouterr().out
    assert "[dry-run]" in out
