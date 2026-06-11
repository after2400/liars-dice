import yaml

from game.components.leaderboard import (
    apply_pending_relegation,
    detect_phase,
    get_tier_players,
    update_leaderboard,
)

# --- apply_pending_relegation ---


def test_apply_pending_moves_player_to_new_tier(lb_with_pending):
    result = apply_pending_relegation(lb_with_pending)
    assert result["players"]["Alice"]["tier"] == "CH"


def test_apply_pending_updates_tier_since(lb_with_pending):
    result = apply_pending_relegation(lb_with_pending)
    assert result["players"]["Alice"]["tier_since"] != "2026-01-01T00:00:00Z"


def test_apply_pending_clears_list(lb_with_pending):
    result = apply_pending_relegation(lb_with_pending)
    assert result["pending_relegation"] == []


def test_apply_pending_empty_list_is_noop(minimal_lb):
    result = apply_pending_relegation(minimal_lb)
    assert result["players"]["Alice"]["tier"] == "PRM"
    assert result["pending_relegation"] == []


# --- detect_phase ---


def test_detect_phase_1_when_below_top_n(minimal_lb):
    assert detect_phase(minimal_lb, top_n=4) == 1


def test_detect_phase_1_when_equal_to_top_n():
    # total == top_n means PRM is exactly full; next entrant still plays PRM and triggers relegation
    data = {
        "players": {
            "A": {"tier": "PRM"},
            "B": {"tier": "PRM"},
            "C": {"tier": "PRM"},
            "D": {"tier": "PRM"},
        }
    }
    assert detect_phase(data, top_n=4) == 1


def test_detect_phase_2_when_between(full_two_tier_lb):
    # 4 total players, TOP_N=2: 4 > 2 and 4 <= 4 → phase 2
    assert detect_phase(full_two_tier_lb, top_n=2) == 2


def test_detect_phase_3_when_above_double(full_two_tier_lb):
    # 4 total players, TOP_N=1: 4 > 2 → phase 3
    assert detect_phase(full_two_tier_lb, top_n=1) == 3


def test_detect_phase_counts_inactive():
    data = {
        "players": {
            "A": {"tier": "PRM"},
            "B": {"tier": "inactive"},
        }
    }
    assert detect_phase(data, top_n=1) == 2  # 2 == 2*1, so phase 2 (inactive counted)


# --- get_tier_players ---


def test_get_tier_players_returns_correct_names(full_two_tier_lb):
    prm = get_tier_players(full_two_tier_lb, "PRM")
    assert set(prm) == {"Alice", "Bruno"}


def test_get_tier_players_empty_when_none(minimal_lb):
    assert get_tier_players(minimal_lb, "CH") == []


def test_get_tier_players_includes_inactive():
    data = {"players": {"X": {"tier": "inactive"}, "Y": {"tier": "PRM"}}}
    assert get_tier_players(data, "inactive") == ["X"]


# --- update_leaderboard ---


def test_update_stats_for_competing_players(lb_file):
    update_leaderboard(
        wins={"Alice": 60, "Bruno": 40},
        n_games=100,
        tier="PRM",
        path=lb_file,
    )
    with open(lb_file) as f:
        result = yaml.safe_load(f)
    prm = result["players"]["Alice"]["tier_stats"]["PRM"]
    assert prm["wins"] == 100  # 40 + 60
    assert prm["games"] == 200  # 100 + 100
    assert prm["win_pct"] == 50.0


def test_update_does_not_touch_non_competing_players(tmp_path, full_two_tier_lb):
    path = str(tmp_path / "lb2.yaml")
    (tmp_path / "lb2.yaml").write_text(
        yaml.dump(full_two_tier_lb, default_flow_style=False, sort_keys=False)
    )
    update_leaderboard(
        wins={"Cleo": 70, "Diego": 30},
        n_games=100,
        tier="CH",
        path=path,
    )
    with open(path) as f:
        result = yaml.safe_load(f)
    assert result["players"]["Alice"]["tier_stats"]["PRM"]["games"] == 100  # unchanged


def test_promotions_change_tier_immediately(lb_file):
    update_leaderboard(
        wins={"Alice": 60, "Bruno": 40},
        n_games=100,
        tier="PRM",
        promotions={"Bruno": "CH"},
        path=lb_file,
    )
    with open(lb_file) as f:
        result = yaml.safe_load(f)
    assert result["players"]["Bruno"]["tier"] == "CH"


def test_pending_relegation_added_to_list(lb_file):
    update_leaderboard(
        wins={"Alice": 60, "Bruno": 40},
        n_games=100,
        tier="PRM",
        pending_relegations=[{"player": "Bruno", "from_tier": "PRM", "to_tier": "CH"}],
        path=lb_file,
    )
    with open(lb_file) as f:
        result = yaml.safe_load(f)
    assert len(result["pending_relegation"]) == 1
    assert result["pending_relegation"][0]["player"] == "Bruno"


def test_times_inactive_incremented(lb_file):
    update_leaderboard(
        wins={"Alice": 60, "Bruno": 40},
        n_games=100,
        tier="L1",
        last_place="Bruno",
        path=lb_file,
    )
    with open(lb_file) as f:
        result = yaml.safe_load(f)
    assert result["players"]["Bruno"]["times_inactive"] == 1


def test_times_inactive_not_incremented_for_other_tiers(lb_file):
    update_leaderboard(
        wins={"Alice": 60, "Bruno": 40},
        n_games=100,
        tier="PRM",
        last_place="Bruno",
        path=lb_file,
    )
    with open(lb_file) as f:
        result = yaml.safe_load(f)
    assert result["players"]["Bruno"]["times_inactive"] == 0


def test_total_runs_incremented(lb_file):
    update_leaderboard(
        wins={"Alice": 60, "Bruno": 40},
        n_games=100,
        tier="PRM",
        path=lb_file,
    )
    with open(lb_file) as f:
        result = yaml.safe_load(f)
    assert result["total_runs"] == 3  # was 2


def test_update_creates_new_player_with_defaults(lb_file):
    """A player absent from the leaderboard is created with correct defaults."""
    update_leaderboard(
        wins={"Alice": 60, "NewPlayer": 40},
        n_games=100,
        tier="CH",
        path=lb_file,
    )
    with open(lb_file) as f:
        result = yaml.safe_load(f)
    assert "NewPlayer" in result["players"]
    np = result["players"]["NewPlayer"]
    ch = np["tier_stats"]["CH"]
    assert ch["wins"] == 40
    assert ch["games"] == 100
    assert ch["win_pct"] == 40.0
    assert np["tier"] == "CH"
    assert np["times_inactive"] == 0
    assert np["display_name"] == "NewPlayer"
    assert np["github_username"] == ""
    assert "date_added" in np


def test_apply_pending_silently_ignores_missing_player():
    """A pending entry for a non-existent player is consumed without error."""
    data = {
        "pending_relegation": [{"player": "Ghost", "from_tier": "PRM", "to_tier": "CH"}],
        "players": {"Alice": {"tier": "PRM", "tier_since": "2026-01-01T00:00:00Z"}},
    }
    result = apply_pending_relegation(data)
    assert result["pending_relegation"] == []  # consumed
    assert result["players"]["Alice"]["tier"] == "PRM"  # unchanged


def test_new_player_entry_has_display_name_and_github_username(lb_file):
    """update_leaderboard creates new players with display_name and github_username."""
    update_leaderboard(
        wins={"NewPlayer": 40},
        n_games=100,
        tier="CH",
        path=lb_file,
    )
    with open(lb_file) as f:
        result = yaml.safe_load(f)
    np = result["players"]["NewPlayer"]
    assert np["display_name"] == "NewPlayer"
    assert np["github_username"] == ""
    assert "times_inactive" in np
    assert "times_last_in_l1" not in np


def test_times_inactive_incremented_on_l1_last_place(lb_file):
    """times_inactive increments when a player finishes last in L1."""
    update_leaderboard(
        wins={"Alice": 60, "Bruno": 40},
        n_games=100,
        tier="L1",
        last_place="Bruno",
        path=lb_file,
    )
    with open(lb_file) as f:
        result = yaml.safe_load(f)
    assert result["players"]["Bruno"]["times_inactive"] == 1


def test_apply_season_results_promotes_top_to_tier_above(tmp_path):
    """Top player promotes; bottom stays when tier ran at capacity with no overcrowding."""
    from game.components.leaderboard import apply_season_results

    lb = {
        "total_runs": 1,
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
            "Bruno": {
                "display_name": "Bruno",
                "github_username": "",
                "tier": "CH",
                "tier_since": "2026-01-01T00:00:00Z",
                "date_added": "2026-01-01T00:00:00Z",
                "times_inactive": 0,
                "tier_stats": {},
            },
        },
        "last_updated": "2026-01-01T00:00:00Z",
    }
    path = str(tmp_path / "lb.yaml")

    (tmp_path / "lb.yaml").write_text(yaml.dump(lb))

    apply_season_results(
        wins={"Alice": 70, "Bruno": 30},
        n_games=100,
        tier="CH",
        top_n=2,
        path=path,
    )
    with open(path) as f:
        result = yaml.safe_load(f)
    assert result["players"]["Alice"]["tier"] == "PRM"  # top CH → PRM
    assert result["players"]["Bruno"]["tier"] == "CH"  # no excess — stays in CH


def test_apply_season_results_promotes_even_when_tier_above_at_capacity(tmp_path):
    """Promotion is unconditional — capacity in tier above is not checked."""
    from game.components.leaderboard import apply_season_results

    lb = {
        "total_runs": 1,
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
            "Bruno": {
                "display_name": "Bruno",
                "github_username": "",
                "tier": "CH",
                "tier_since": "2026-01-01T00:00:00Z",
                "date_added": "2026-01-01T00:00:00Z",
                "times_inactive": 0,
                "tier_stats": {},
            },
            # PRM is already at capacity (top_n=2)
            "Cleo": {
                "display_name": "Cleo",
                "github_username": "",
                "tier": "PRM",
                "tier_since": "2026-01-01T00:00:00Z",
                "date_added": "2026-01-01T00:00:00Z",
                "times_inactive": 0,
                "tier_stats": {},
            },
            "Diego": {
                "display_name": "Diego",
                "github_username": "",
                "tier": "PRM",
                "tier_since": "2026-01-01T00:00:00Z",
                "date_added": "2026-01-01T00:00:00Z",
                "times_inactive": 0,
                "tier_stats": {},
            },
        },
        "last_updated": "2026-01-01T00:00:00Z",
    }
    path = str(tmp_path / "lb.yaml")

    (tmp_path / "lb.yaml").write_text(yaml.dump(lb))

    apply_season_results(
        wins={"Alice": 70, "Bruno": 30},
        n_games=100,
        tier="CH",
        top_n=2,
        path=path,
    )
    with open(path) as f:
        result = yaml.safe_load(f)
    # Alice promotes to PRM even though PRM was already full
    assert result["players"]["Alice"]["tier"] == "PRM"


def test_apply_season_results_no_relegation_from_prm_at_exact_capacity(tmp_path):
    """PRM at exact capacity with no CH promotion: both players stay."""
    from game.components.leaderboard import apply_season_results

    lb = {
        "total_runs": 1,
        "players": {
            "Alice": {
                "display_name": "Alice",
                "github_username": "",
                "tier": "PRM",
                "tier_since": "2026-01-01T00:00:00Z",
                "date_added": "2026-01-01T00:00:00Z",
                "times_inactive": 0,
                "tier_stats": {},
            },
            "Bruno": {
                "display_name": "Bruno",
                "github_username": "",
                "tier": "PRM",
                "tier_since": "2026-01-01T00:00:00Z",
                "date_added": "2026-01-01T00:00:00Z",
                "times_inactive": 0,
                "tier_stats": {},
            },
        },
        "last_updated": "2026-01-01T00:00:00Z",
    }
    path = str(tmp_path / "lb.yaml")

    (tmp_path / "lb.yaml").write_text(yaml.dump(lb))

    apply_season_results(
        wins={"Alice": 70, "Bruno": 30},
        n_games=100,
        tier="PRM",
        top_n=2,
        path=path,
    )
    with open(path) as f:
        result = yaml.safe_load(f)
    assert result["players"]["Alice"]["tier"] == "PRM"  # stays
    assert result["players"]["Bruno"]["tier"] == "PRM"  # no excess — stays


def test_apply_season_results_no_relegation_when_promotion_restores_capacity(tmp_path):
    """CH at capacity+1: promoting the top brings it back to capacity — no further relegation."""

    from game.components.leaderboard import apply_season_results

    def _player(tier):
        return {
            "display_name": "",
            "github_username": "",
            "tier": tier,
            "tier_since": "2026-01-01T00:00:00Z",
            "date_added": "2026-01-01T00:00:00Z",
            "times_inactive": 0,
            "tier_stats": {},
        }

    # top_n=4, so CH capacity=4. Start with 5 in CH (e.g. L1 promoted someone in).
    lb = {
        "total_runs": 1,
        "players": {
            "P1": _player("CH"),
            "P2": _player("CH"),
            "P3": _player("CH"),
            "P4": _player("CH"),
            "P5": _player("CH"),
        },
        "last_updated": "2026-01-01T00:00:00Z",
    }
    path = str(tmp_path / "lb.yaml")
    (tmp_path / "lb.yaml").write_text(yaml.dump(lb))

    apply_season_results(
        wins={"P1": 50, "P2": 40, "P3": 30, "P4": 20, "P5": 0},
        n_games=100,
        tier="CH",
        top_n=4,
        path=path,
    )
    with open(path) as f:
        result = yaml.safe_load(f)

    assert result["players"]["P1"]["tier"] == "PRM"  # top promotes
    assert result["players"]["P2"]["tier"] == "CH"  # remaining 4 = capacity, no excess
    assert result["players"]["P3"]["tier"] == "CH"
    assert result["players"]["P4"]["tier"] == "CH"
    assert result["players"]["P5"]["tier"] == "CH"  # stays — promotion restored capacity


def test_apply_season_results_relegates_when_truly_overcrowded(tmp_path):
    """CH at capacity+2: after promoting top, still 1 player over — relegate that one."""

    from game.components.leaderboard import apply_season_results

    def _player(tier):
        return {
            "display_name": "",
            "github_username": "",
            "tier": tier,
            "tier_since": "2026-01-01T00:00:00Z",
            "date_added": "2026-01-01T00:00:00Z",
            "times_inactive": 0,
            "tier_stats": {},
        }

    # top_n=4, so CH capacity=4. Start with 6 in CH (capacity+2).
    lb = {
        "total_runs": 1,
        "players": {f"P{i}": _player("CH") for i in range(1, 7)},
        "last_updated": "2026-01-01T00:00:00Z",
    }
    path = str(tmp_path / "lb.yaml")
    (tmp_path / "lb.yaml").write_text(yaml.dump(lb))

    apply_season_results(
        wins={"P1": 60, "P2": 50, "P3": 40, "P4": 30, "P5": 10, "P6": 0},
        n_games=100,
        tier="CH",
        top_n=4,
        path=path,
    )
    with open(path) as f:
        result = yaml.safe_load(f)

    assert result["players"]["P1"]["tier"] == "PRM"  # top promotes
    assert result["players"]["P6"]["tier"] == "L1"  # 1 excess after promotion → relegated
    assert result["players"]["P2"]["tier"] == "CH"
    assert result["players"]["P3"]["tier"] == "CH"
    assert result["players"]["P4"]["tier"] == "CH"
    assert result["players"]["P5"]["tier"] == "CH"  # exactly at capacity now


def test_apply_season_results_no_relegation_when_tier_below_capacity(tmp_path):
    """L1 (or any thin tier) does not force a relegation when started below capacity."""

    from game.components.leaderboard import apply_season_results

    def _player(tier):
        return {
            "display_name": "",
            "github_username": "",
            "tier": tier,
            "tier_since": "2026-01-01T00:00:00Z",
            "date_added": "2026-01-01T00:00:00Z",
            "times_inactive": 0,
            "tier_stats": {},
        }

    # top_n=4, so L1 capacity=8. Only 2 players — well below capacity.
    lb = {
        "total_runs": 1,
        "players": {"P1": _player("L1"), "P2": _player("L1")},
        "last_updated": "2026-01-01T00:00:00Z",
    }
    path = str(tmp_path / "lb.yaml")
    (tmp_path / "lb.yaml").write_text(yaml.dump(lb))

    apply_season_results(
        wins={"P1": 70, "P2": 30},
        n_games=100,
        tier="L1",
        top_n=4,
        path=path,
    )
    with open(path) as f:
        result = yaml.safe_load(f)

    assert result["players"]["P1"]["tier"] == "CH"  # top promotes
    assert result["players"]["P2"]["tier"] == "L1"  # stays — L1 is below capacity, no relegation


# --- build_display_names ---


def test_build_display_names_unique_names_unsuffixed():
    from game.components.leaderboard import build_display_names

    players = {
        "Alice": {"display_name": "Alice", "github_username": "x"},
        "Bruno": {"display_name": "Bruno", "github_username": "y"},
    }
    assert build_display_names(players) == {"Alice": "Alice", "Bruno": "Bruno"}


def test_build_display_names_distinct_usernames_get_suffix():
    from game.components.leaderboard import build_display_names

    players = {
        "TopperA": {"display_name": "Topper", "github_username": "after2400"},
        "TopperB": {"display_name": "Topper", "github_username": "jschmoe"},
    }
    assert build_display_names(players) == {
        "TopperA": "Topper (after2400)",
        "TopperB": "Topper (jschmoe)",
    }


def test_build_display_names_empty_username_falls_back_to_class():
    from game.components.leaderboard import build_display_names

    players = {
        "TopperA": {"display_name": "Topper", "github_username": "after2400"},
        "TopperB": {"display_name": "Topper", "github_username": ""},
    }
    assert build_display_names(players) == {
        "TopperA": "Topper (after2400)",
        "TopperB": "Topper (TopperB)",
    }


def test_build_display_names_both_empty_use_class():
    from game.components.leaderboard import build_display_names

    players = {
        "TopperA": {"display_name": "Topper", "github_username": ""},
        "TopperB": {"display_name": "Topper", "github_username": ""},
    }
    assert build_display_names(players) == {
        "TopperA": "Topper (TopperA)",
        "TopperB": "Topper (TopperB)",
    }


def test_build_display_names_same_author_uses_class():
    from game.components.leaderboard import build_display_names

    players = {
        "TopperA": {"display_name": "Topper", "github_username": "after2400"},
        "TopperB": {"display_name": "Topper", "github_username": "after2400"},
    }
    assert build_display_names(players) == {
        "TopperA": "Topper (TopperA)",
        "TopperB": "Topper (TopperB)",
    }


def test_build_display_names_mixed_collision_and_unique():
    from game.components.leaderboard import build_display_names

    players = {
        "TopperA": {"display_name": "Topper", "github_username": "after2400"},
        "TopperB": {"display_name": "Topper", "github_username": "jschmoe"},
        "Alice": {"display_name": "Alice", "github_username": ""},
    }
    result = build_display_names(players)
    assert result["Alice"] == "Alice"
    assert result["TopperA"] == "Topper (after2400)"
    assert result["TopperB"] == "Topper (jschmoe)"


def test_build_display_names_missing_display_name_uses_class():
    from game.components.leaderboard import build_display_names

    players = {"Solo": {"github_username": "x"}}
    assert build_display_names(players) == {"Solo": "Solo"}


def test_apply_season_results_movement_uses_disambiguated_name(tmp_path):
    from game.components.leaderboard import apply_season_results

    path = str(tmp_path / "lb.yaml")
    data = {
        "total_runs": 0,
        "players": {
            "TopperA": {
                "display_name": "Topper",
                "github_username": "alice",
                "tier": "CH",
                "tier_since": "2026-01-01T00:00:00Z",
                "tier_stats": {},
            },
            "TopperB": {
                "display_name": "Topper",
                "github_username": "bob",
                "tier": "CH",
                "tier_since": "2026-01-01T00:00:00Z",
                "tier_stats": {},
            },
        },
    }
    (tmp_path / "lb.yaml").write_text(yaml.dump(data))

    movements = apply_season_results(
        {"TopperA": 10, "TopperB": 2}, n_games=10, tier="CH", top_n=4, path=path
    )

    # TopperA wins most → promoted; message uses the disambiguated name.
    assert "Promoted: Topper (alice) → PRM" in movements


def test_build_display_names_no_op_on_current_leaderboard():
    """Every current display name is unique, so the helper adds no suffixes.

    This test will (correctly) start failing if a duplicate display_name is ever
    registered — that is expected, and means the helper should now be adding
    disambiguating suffixes.
    """
    from pathlib import Path

    from game.components.leaderboard import build_display_names

    repo_root = Path(__file__).parent.parent
    data = yaml.safe_load((repo_root / "leaderboard.yaml").read_text())
    players = data["players"]

    result = build_display_names(players)
    for cn, p in players.items():
        assert result[cn] == p.get("display_name", cn)  # bare, no suffix added


# --- settle_relegations ---


def _p(tier, since="2026-01-01T00:00:00Z", games=0):
    """Minimal player record for settlement tests."""
    return {
        "display_name": None,  # filled in by caller via dict key below
        "github_username": "",
        "date_added": "2026-01-01T00:00:00Z",
        "tier": tier,
        "tier_since": since,
        "times_inactive": 0,
        "tier_stats": {tier: {"wins": 0, "games": games, "win_pct": 0.0}} if games else {},
    }


def _write(tmp_path, players):
    for name, rec in players.items():
        rec["display_name"] = name
    data = {"total_runs": 1, "last_updated": "2026-01-01T00:00:00Z", "players": players}
    path = str(tmp_path / "lb.yaml")
    (tmp_path / "lb.yaml").write_text(yaml.dump(data))
    return path


def test_settle_cascade_one_pass(tmp_path):
    """PRM overflow drops to CH; CH then overflows and drops its worst player to L1."""
    from game.components.leaderboard import settle_relegations

    players = {
        # PRM has 5 (one too many): Remy is the parachutee-to-be (worst this run)
        "Diego": _p("PRM"),
        "Eva": _p("PRM"),
        "Sloane": _p("PRM"),
        "Zara": _p("PRM"),
        "Remy": _p("PRM"),
        # CH has 4 incl. Cleo (promoted in this run, flopped); Alice/Bruno/Finn natives
        "Alice": _p("CH"),
        "Bruno": _p("CH"),
        "Finn": _p("CH"),
        "Cleo": _p("CH"),
        # L1 under capacity
        "Pyro": _p("L1"),
        "Topper": _p("L1"),
    }
    path = _write(tmp_path, players)
    tier_results = {
        "PRM": {"Sloane": 240, "Eva": 235, "Zara": 217, "Diego": 202, "Remy": 106},
        "CH": {"Remy": 337, "Finn": 312, "Alice": 194, "Bruno": 153, "Cleo": 4},
        "L1": {"Cleo": 471, "Topper": 444, "Pyro": 85},
    }
    moves = settle_relegations(tier_results, top_n=4, path=path)

    with open(path) as f:
        result = yaml.safe_load(f)["players"]
    assert result["Remy"]["tier"] == "CH"  # PRM → CH
    assert result["Cleo"]["tier"] == "L1"  # CH → L1 (worst CH player)
    assert {n for n, p in result.items() if p["tier"] == "PRM"} == {
        "Diego",
        "Eva",
        "Sloane",
        "Zara",
    }
    assert {n for n, p in result.items() if p["tier"] == "CH"} == {"Alice", "Bruno", "Finn", "Remy"}
    assert {n for n, p in result.items() if p["tier"] == "L1"} == {"Pyro", "Topper", "Cleo"}
    assert moves == ["Relegated: Remy → CH", "Relegated: Cleo → L1"]


def test_settle_protects_parachutist(tmp_path):
    """A player dropped from above is not re-dropped; the worst native drops instead."""
    from game.components.leaderboard import settle_relegations

    players = {
        "Diego": _p("PRM"),
        "Eva": _p("PRM"),
        "Sloane": _p("PRM"),
        "Zara": _p("PRM"),
        "Remy": _p("PRM"),
        "Alice": _p("CH"),
        "Bruno": _p("CH"),
        "Finn": _p("CH"),
        "Cleo": _p("CH"),
        "Pyro": _p("L1"),
        "Topper": _p("L1"),
    }
    path = _write(tmp_path, players)
    # Remy wins CH big (337) — if he were eligible in CH he'd be safe anyway; the point is
    # he is excluded as a parachutist, so the worst native (Cleo) drops even though Remy
    # also has a CH result this run.
    tier_results = {
        "PRM": {"Sloane": 240, "Eva": 235, "Zara": 217, "Diego": 202, "Remy": 106},
        "CH": {"Remy": 337, "Finn": 312, "Alice": 194, "Bruno": 153, "Cleo": 4},
    }
    settle_relegations(tier_results, top_n=4, path=path)
    with open(path) as f:
        result = yaml.safe_load(f)["players"]
    assert result["Remy"]["tier"] == "CH"  # stayed where he parachuted
    assert result["Cleo"]["tier"] == "L1"  # native worst dropped


def test_settle_no_relegation_at_capacity(tmp_path):
    """Tiers at or under capacity shed nobody."""
    from game.components.leaderboard import settle_relegations

    players = {
        "Alice": _p("PRM"),
        "Bruno": _p("PRM"),
        "Cleo": _p("CH"),
        "Diego": _p("CH"),
    }
    path = _write(tmp_path, players)
    tier_results = {"PRM": {"Alice": 70, "Bruno": 30}, "CH": {"Cleo": 60, "Diego": 40}}
    moves = settle_relegations(tier_results, top_n=2, path=path)
    assert moves == []
    with open(path) as f:
        result = yaml.safe_load(f)["players"]
    assert all(
        result[n]["tier"] == t
        for n, t in {"Alice": "PRM", "Bruno": "PRM", "Cleo": "CH", "Diego": "CH"}.items()
    )


def test_settle_l1_to_inactive_only_when_over_double(tmp_path):
    """L1 relegates to inactive only past TOP_N×2, and increments times_inactive."""
    from game.components.leaderboard import settle_relegations

    # TOP_N=2 → L1 capacity 4. Five L1 players → one drops to inactive.
    players = {f"P{i}": _p("L1") for i in range(5)}
    path = _write(tmp_path, players)
    tier_results = {"L1": {"P0": 50, "P1": 40, "P2": 30, "P3": 20, "P4": 5}}
    moves = settle_relegations(tier_results, top_n=2, path=path)
    with open(path) as f:
        result = yaml.safe_load(f)["players"]
    assert result["P4"]["tier"] == "inactive"  # worst L1 player
    assert result["P4"]["times_inactive"] == 1
    assert moves == ["Relegated: P4 → inactive"]


def test_settle_movement_uses_disambiguated_name(tmp_path):
    """Movement strings render disambiguated display names for shared names."""
    from game.components.leaderboard import settle_relegations

    players = {
        "Eva": _p("PRM"),
        "Zara": _p("PRM"),
        "Sloane": _p("PRM"),
        "Diego": _p("PRM"),
        "Remy": _p("PRM"),
        "Alice": _p("CH"),
        "Bruno": _p("CH"),
    }
    for name, rec in players.items():
        rec["display_name"] = name
    # Two players share display_name "Twin" so the suffix logic engages.
    players["Remy"]["display_name"] = "Twin"
    players["Alice"]["display_name"] = "Twin"
    players["Remy"]["github_username"] = "remy_gh"
    data = {"total_runs": 1, "last_updated": "2026-01-01T00:00:00Z", "players": players}
    path = str(tmp_path / "lb.yaml")
    (tmp_path / "lb.yaml").write_text(yaml.dump(data))

    tier_results = {"PRM": {"Eva": 50, "Zara": 40, "Sloane": 30, "Diego": 20, "Remy": 5}}
    moves = settle_relegations(tier_results, top_n=4, path=path)
    assert moves == ["Relegated: Twin (remy_gh) → CH"]
