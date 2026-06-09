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
    import yaml as _yaml

    path = str(tmp_path / "lb2.yaml")
    (tmp_path / "lb2.yaml").write_text(
        _yaml.dump(full_two_tier_lb, default_flow_style=False, sort_keys=False)
    )
    update_leaderboard(
        wins={"Cleo": 70, "Diego": 30},
        n_games=100,
        tier="CH",
        path=path,
    )
    with open(path) as f:
        result = _yaml.safe_load(f)
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
    """apply_season_results moves the top player up immediately."""
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
    import yaml as _yaml

    (tmp_path / "lb.yaml").write_text(_yaml.dump(lb))

    apply_season_results(
        wins={"Alice": 70, "Bruno": 30},
        n_games=100,
        tier="CH",
        top_n=2,
        path=path,
    )
    with open(path) as f:
        result = _yaml.safe_load(f)
    assert result["players"]["Alice"]["tier"] == "PRM"  # top CH → PRM
    assert result["players"]["Bruno"]["tier"] == "CH"  # stays


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
    import yaml as _yaml

    (tmp_path / "lb.yaml").write_text(_yaml.dump(lb))

    apply_season_results(
        wins={"Alice": 70, "Bruno": 30},
        n_games=100,
        tier="CH",
        top_n=2,
        path=path,
    )
    with open(path) as f:
        result = _yaml.safe_load(f)
    # Alice promotes to PRM even though PRM was already full
    assert result["players"]["Alice"]["tier"] == "PRM"


def test_apply_season_results_relegates_bottom(tmp_path):
    """apply_season_results moves the bottom player down immediately."""
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
    import yaml as _yaml

    (tmp_path / "lb.yaml").write_text(_yaml.dump(lb))

    apply_season_results(
        wins={"Alice": 70, "Bruno": 30},
        n_games=100,
        tier="PRM",
        top_n=2,
        path=path,
    )
    with open(path) as f:
        result = _yaml.safe_load(f)
    assert result["players"]["Bruno"]["tier"] == "CH"  # bottom PRM → CH
    assert result["players"]["Alice"]["tier"] == "PRM"  # stays
