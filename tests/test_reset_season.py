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
            tier: {"wins": wins, "games": games, "win_pct": round(wins / games * 100, 1)}
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
