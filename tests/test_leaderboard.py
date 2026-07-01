from collections import namedtuple as _nt

import yaml

from game.components.leaderboard import (
    get_tier_players,
)

# --- get_tier_players ---


def test_get_tier_players_returns_correct_names(full_two_tier_lb):
    prm = get_tier_players(full_two_tier_lb, "PRM")
    assert set(prm) == {"Alice", "Bruno"}


def test_get_tier_players_empty_when_none(minimal_lb):
    assert get_tier_players(minimal_lb, "CH") == []


def test_get_tier_players_includes_inactive():
    data = {"players": {"X": {"tier": "inactive"}, "Y": {"tier": "PRM"}}}
    assert get_tier_players(data, "inactive") == ["X"]


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


# --- H2H tiebreaker ---

# Die exchange data extracted from a real 500-game PRM session (Oracle, Nuke LaLoosh,
# Stewie screenshot). Verified: column sums = 0 (every exchange counted from both sides).
#
#  Oracle vs Nuke:   Lost B/C=269/100  Won B/C=208/189  Net +28
#  Oracle vs Stewie: Lost B/C=238/113  Won B/C=178/126  Net -47  → Oracle aggregate: -19
#  Nuke   vs Oracle: Lost B/C=208/189  Won B/C=269/100  Net -28
#  Nuke   vs Stewie: Lost B/C=214/152  Won B/C=230/135  Net  -1  → Nuke   aggregate: -29
#  Stewie vs Oracle: Lost B/C=178/126  Won B/C=238/113  Net +47
#  Stewie vs Nuke:   Lost B/C=230/135  Won B/C=214/152  Net  +1  → Stewie aggregate: +48

_MockStats = _nt("_MockStats", ["die_losses_from_bluff", "die_losses_from_challenge"])

_SAMPLE_STATS = _MockStats(
    die_losses_from_bluff={
        "Oracle": {"Nuke": 269, "Stewie": 238},
        "Nuke": {"Oracle": 208, "Stewie": 214},
        "Stewie": {"Oracle": 178, "Nuke": 230},
    },
    die_losses_from_challenge={
        "Oracle": {"Nuke": 100, "Stewie": 113},
        "Nuke": {"Oracle": 189, "Stewie": 152},
        "Stewie": {"Oracle": 126, "Nuke": 135},
    },
)


def test_h2h_aggregate_sample_data():
    """_h2h_aggregate matches the +28/-47/-1/+47/+1/-28 values from the screenshot."""
    from game.components.leaderboard import _h2h_aggregate

    group = ["Oracle", "Nuke", "Stewie"]
    assert _h2h_aggregate("Oracle", group, _SAMPLE_STATS) == -19  # +28 + -47
    assert _h2h_aggregate("Nuke", group, _SAMPLE_STATS) == -29  # -28 + -1
    assert _h2h_aggregate("Stewie", group, _SAMPLE_STATS) == +48  # +47 + +1
    # Sanity: the three aggregates must sum to zero
    total = sum(_h2h_aggregate(n, group, _SAMPLE_STATS) for n in group)
    assert total == 0


def test_h2h_aggregate_name_map_translates_class_to_display():
    """When class names differ from display names, name_map bridges the gap.

    Without name_map, lookups against display-name-keyed stats silently return
    0 for every player whose class name != display name.
    """
    from game.components.leaderboard import _h2h_aggregate

    # Class names are different from the display names in _SAMPLE_STATS
    name_map = {"OracleBot": "Oracle", "NukeLaLoosh": "Nuke", "EvilStewie": "Stewie"}
    group = ["OracleBot", "NukeLaLoosh", "EvilStewie"]

    # Without name_map every lookup misses → all zeros
    assert _h2h_aggregate("OracleBot", group, _SAMPLE_STATS) == 0
    assert _h2h_aggregate("NukeLaLoosh", group, _SAMPLE_STATS) == 0

    # With name_map results match the display-name variants exactly
    assert _h2h_aggregate("OracleBot", group, _SAMPLE_STATS, name_map=name_map) == -19
    assert _h2h_aggregate("NukeLaLoosh", group, _SAMPLE_STATS, name_map=name_map) == -29
    assert _h2h_aggregate("EvilStewie", group, _SAMPLE_STATS, name_map=name_map) == +48
    total = sum(_h2h_aggregate(n, group, _SAMPLE_STATS, name_map=name_map) for n in group)
    assert total == 0


def test_settle_h2h_breaks_two_way_win_tie_relegates_nuke(tmp_path):
    """Oracle and Nuke both at 58 wins — H2H (+28 Oracle over Nuke) sends Nuke down."""
    from game.components.leaderboard import settle_relegations

    players = {
        "Alice": _p("PRM"),
        "Bruno": _p("PRM"),
        "Cleo": _p("PRM"),
        "Oracle": _p("PRM"),
        "Nuke": _p("PRM"),
    }
    path = _write(tmp_path, players)

    # top_n=4, 5 players → capacity=4, excess=1. Alice/Bruno/Cleo safe; Oracle vs Nuke
    # tied at 20 wins. Without H2H the tiebreak would be tier_since (identical), so
    # result is undefined. With H2H, Oracle dominates Nuke → Nuke relegated.
    tier_results = {"PRM": {"Alice": 80, "Bruno": 70, "Cleo": 60, "Oracle": 20, "Nuke": 20}}
    moves = settle_relegations(
        tier_results,
        top_n=4,
        path=path,
        tier_stats={"PRM": _SAMPLE_STATS},
    )

    with open(path) as f:
        result = yaml.safe_load(f)["players"]
    assert result["Nuke"]["tier"] == "CH"
    assert result["Oracle"]["tier"] == "PRM"
    assert moves == ["Relegated: Nuke → CH"]


def test_settle_h2h_three_way_win_tie_relegates_nuke(tmp_path):
    """Oracle, Nuke, and Stewie all at 20 wins. Nuke (aggregate -29) is worst; Oracle
    (-19) and Stewie (+48) stay. Capacity=4 with 5 players forces exactly 1 relegation."""
    from game.components.leaderboard import settle_relegations

    players = {
        "Alice": _p("PRM"),
        "Bruno": _p("PRM"),
        "Oracle": _p("PRM"),
        "Nuke": _p("PRM"),
        "Stewie": _p("PRM"),
    }
    path = _write(tmp_path, players)

    tier_results = {"PRM": {"Alice": 80, "Bruno": 70, "Oracle": 20, "Nuke": 20, "Stewie": 20}}
    moves = settle_relegations(
        tier_results,
        top_n=4,
        path=path,
        tier_stats={"PRM": _SAMPLE_STATS},
    )

    with open(path) as f:
        result = yaml.safe_load(f)["players"]
    assert result["Nuke"]["tier"] == "CH"
    assert result["Oracle"]["tier"] == "PRM"
    assert result["Stewie"]["tier"] == "PRM"
    assert moves == ["Relegated: Nuke → CH"]


def test_settle_h2h_not_used_when_wins_differ(tmp_path):
    """H2H is only a tiebreaker — never overrides a real win difference."""
    from game.components.leaderboard import settle_relegations

    players = {
        "Alice": _p("PRM"),
        "Bruno": _p("PRM"),
        "Cleo": _p("PRM"),
        "Oracle": _p("PRM"),
        "Nuke": _p("PRM"),
    }
    path = _write(tmp_path, players)

    # Nuke has FEWER wins than Oracle, so Nuke is relegated regardless of H2H advantage.
    # _SAMPLE_STATS gives Oracle net +28 over Nuke, but wins dominate.
    tier_results = {"PRM": {"Alice": 80, "Bruno": 70, "Cleo": 60, "Oracle": 30, "Nuke": 10}}
    settle_relegations(
        tier_results,
        top_n=4,
        path=path,
        tier_stats={"PRM": _SAMPLE_STATS},
    )

    with open(path) as f:
        result = yaml.safe_load(f)["players"]
    assert result["Nuke"]["tier"] == "CH"
    assert result["Oracle"]["tier"] == "PRM"


def test_settle_h2h_falls_back_gracefully_without_stats(tmp_path):
    """When tier_stats is None the sort degrades to (wins, tier_games, tier_since) — no error."""
    from game.components.leaderboard import settle_relegations

    # 5 PRM + 6 others = 11 total → tier_capacities(11)["PRM"]=4 → excess=1
    players = {
        "Alice": _p("PRM"),
        "Bruno": _p("PRM"),
        "Cleo": _p("PRM"),
        "Diana": _p("PRM"),
        "Eve": _p("PRM"),
        **{f"L{i}": _p("L1") for i in range(6)},
    }
    path = _write(tmp_path, players)

    tier_results = {"PRM": {"Alice": 70, "Bruno": 60, "Cleo": 50, "Diana": 40, "Eve": 10}}
    moves = settle_relegations(tier_results, top_n=4, path=path, tier_stats=None)

    with open(path) as f:
        result = yaml.safe_load(f)["players"]
    assert result["Eve"]["tier"] == "CH"  # worst wins, no H2H needed
    assert moves == ["Relegated: Eve → CH"]


# --- avatar_img_tag ---


def test_avatar_img_tag_uses_cloudinary_when_avatar_set():
    from game.components.leaderboard import avatar_img_tag

    player = {"avatar": "hdyiihba/The_Merovingian_200x200_rqd12y.png"}
    tag = avatar_img_tag("Merovingian", player)
    assert (
        'src="https://res.cloudinary.com/hdyiihba/image/upload/'
        'w_64,h_64,c_fill/The_Merovingian_200x200_rqd12y.png"' in tag
    )


def test_avatar_img_tag_falls_back_to_gravatar_when_absent():
    import hashlib

    from game.components.leaderboard import avatar_img_tag

    player = {}
    tag = avatar_img_tag("Alice", player)
    synthetic_hash = hashlib.md5(b"Alice", usedforsecurity=False).hexdigest()
    assert f'src="https://www.gravatar.com/avatar/{synthetic_hash}?d=identicon&f=y&s=64"' in tag


def test_avatar_img_tag_fallback_is_deterministic():
    from game.components.leaderboard import avatar_img_tag

    tag1 = avatar_img_tag("Alice", {})
    tag2 = avatar_img_tag("Alice", {})
    assert tag1 == tag2


def test_avatar_img_tag_fallback_differs_per_class_name():
    from game.components.leaderboard import avatar_img_tag

    tag_alice = avatar_img_tag("Alice", {})
    tag_bruno = avatar_img_tag("Bruno", {})
    assert tag_alice != tag_bruno


def test_avatar_img_tag_respects_size_param_for_cloudinary():
    from game.components.leaderboard import avatar_img_tag

    player = {"avatar": "hdyiihba/The_Merovingian_200x200_rqd12y.png"}
    tag = avatar_img_tag("Merovingian", player, size=32)
    assert "w_32,h_32,c_fill" in tag
    assert 'width="32" height="32"' in tag


def test_avatar_img_tag_respects_size_param_for_gravatar_fallback():
    from game.components.leaderboard import avatar_img_tag

    tag = avatar_img_tag("Alice", {}, size=32)
    assert "s=32" in tag
    assert 'width="32" height="32"' in tag


def test_avatar_img_tag_default_size_is_64():
    from game.components.leaderboard import avatar_img_tag

    tag = avatar_img_tag("Alice", {})
    assert 'width="64" height="64"' in tag


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
    # Remy is relegated PRM→CH (parachutist) AND has the worst CH result this run (2).
    # Without protection he'd be the one dropped to L1; protection excludes him, so the
    # worst NATIVE player (Cleo, 4) drops instead. This fails if the `protected` check is removed.
    tier_results = {
        "PRM": {"Sloane": 240, "Eva": 235, "Zara": 217, "Diego": 202, "Remy": 106},
        "CH": {"Finn": 312, "Alice": 194, "Bruno": 153, "Cleo": 4, "Remy": 2},
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


def test_apply_season_results_does_not_relegate_when_overcrowded(tmp_path):
    """apply_season_results promotes the winner but never relegates — even when overcrowded."""
    from game.components.leaderboard import apply_season_results

    def _player(tier):
        return {
            "display_name": None,
            "github_username": "",
            "tier": tier,
            "tier_since": "2026-01-01T00:00:00Z",
            "date_added": "2026-01-01T00:00:00Z",
            "times_inactive": 0,
            "tier_stats": {},
        }

    # CH overcrowded: 4 players, capacity TOP_N=2.
    # After promoting Alice the old code would see remaining=3 > capacity=2 → excess=1
    # and would relegate Cleo.  The new code must NOT do that.
    players = {
        "Alice": _player("CH"),
        "Bruno": _player("CH"),
        "Cleo": _player("CH"),
        "Dana": _player("CH"),
    }
    for n, rec in players.items():
        rec["display_name"] = n
    lb = {"total_runs": 1, "last_updated": "2026-01-01T00:00:00Z", "players": players}
    path = str(tmp_path / "lb.yaml")
    (tmp_path / "lb.yaml").write_text(yaml.dump(lb))

    apply_season_results(
        wins={"Alice": 70, "Bruno": 20, "Cleo": 10, "Dana": 5},
        n_games=100,
        tier="CH",
        top_n=2,
        path=path,
    )
    with open(path) as f:
        result = yaml.safe_load(f)["players"]
    assert result["Alice"]["tier"] == "PRM"  # winner still promoted
    assert result["Bruno"]["tier"] == "CH"  # NOT relegated
    assert result["Cleo"]["tier"] == "CH"  # NOT relegated (settlement's job now)
    assert result["Dana"]["tier"] == "CH"  # NOT relegated


# --- tier_capacities ---


def test_tier_capacities_phase1_empty():
    from game.components.leaderboard import tier_capacities

    caps = tier_capacities(8)
    assert caps == {"PRM": 4, "CH": 4, "L1": 0, "DED": 0}


def test_tier_capacities_phase1_current():
    from game.components.leaderboard import tier_capacities

    caps = tier_capacities(11)
    assert caps == {"PRM": 4, "CH": 4, "L1": 3, "DED": 0}


def test_tier_capacities_phase1_full():
    from game.components.leaderboard import tier_capacities

    # L1 fills to 8 at n=16; PRM/CH growth begins next
    caps = tier_capacities(16)
    assert caps == {"PRM": 4, "CH": 4, "L1": 8, "DED": 0}


def test_tier_capacities_phase2_mid():
    from game.components.leaderboard import tier_capacities

    # n=20: PRM and CH have each grown 2 seats; L1 frozen at 8
    caps = tier_capacities(20)
    assert caps == {"PRM": 6, "CH": 6, "L1": 8, "DED": 0}


def test_tier_capacities_phase2_full():
    from game.components.leaderboard import tier_capacities

    # n=24: PRM/CH both reach 8; all tiers at 8/8/8
    caps = tier_capacities(24)
    assert caps == {"PRM": 8, "CH": 8, "L1": 8, "DED": 0}


def test_tier_capacities_phase3_odd():
    from game.components.leaderboard import tier_capacities

    # n=25: L1 resumes growth
    caps = tier_capacities(25)
    assert caps == {"PRM": 8, "CH": 8, "L1": 9, "DED": 0}


def test_tier_capacities_phase3_even():
    from game.components.leaderboard import tier_capacities

    caps = tier_capacities(26)
    assert caps == {"PRM": 8, "CH": 8, "L1": 10, "DED": 0}


def test_tier_capacities_phase3_full():
    from game.components.leaderboard import tier_capacities

    caps = tier_capacities(32)
    assert caps == {"PRM": 8, "CH": 8, "L1": 16, "DED": 0}


def test_tier_capacities_phase3():
    from game.components.leaderboard import tier_capacities

    caps = tier_capacities(64)
    assert caps == {"PRM": 8, "CH": 8, "L1": 16, "DED": 32}


# --- detect_entry_tier ---


def test_detect_entry_tier_empty_lb_returns_ch():
    from game.components.leaderboard import detect_entry_tier

    lb = {"players": {}}
    assert detect_entry_tier(lb) == "CH"


def test_detect_entry_tier_l1_has_room():
    from game.components.leaderboard import detect_entry_tier

    # With 11 current players, cap for #12 = tier_capacities(12) = L1=4, current L1=3 < 4 → L1
    players = {f"P{i}": {"tier": "PRM"} for i in range(4)}
    players.update({f"C{i}": {"tier": "CH"} for i in range(4)})
    players.update({f"L{i}": {"tier": "L1"} for i in range(3)})
    lb = {"players": players}
    assert detect_entry_tier(lb) == "L1"


def test_detect_entry_tier_l1_overcrowded_still_returns_l1():
    from game.components.leaderboard import detect_entry_tier

    # 24 players with L1 overcrowded. For #25: L1 cap=9 > 0, so still L1.
    # Season run will relegate the bottom to restore balance.
    players = {f"P{i}": {"tier": "PRM"} for i in range(4)}
    players.update({f"C{i}": {"tier": "CH"} for i in range(4)})
    players.update({f"L{i}": {"tier": "L1"} for i in range(16)})  # 24 players
    lb = {"players": players}
    assert detect_entry_tier(lb) == "L1"


def test_detect_entry_tier_l1_full_at_32_still_returns_l1():
    from game.components.leaderboard import detect_entry_tier

    # 32 players at capacity. For #33: tier_capacities(33)={PRM:8,CH:8,L1:16,DED:1}.
    # L1 cap=16 > 0, so enter L1 (temporarily over-cap); season run corrects.
    players = {f"P{i}": {"tier": "PRM"} for i in range(8)}
    players.update({f"C{i}": {"tier": "CH"} for i in range(8)})
    players.update({f"L{i}": {"tier": "L1"} for i in range(16)})
    lb = {"players": players}
    assert detect_entry_tier(lb) == "L1"


def test_detect_entry_tier_overcrowded_league_still_returns_l1():
    from game.components.leaderboard import detect_entry_tier

    # All tiers overcrowded (pathological). tier_capacities(41)={PRM:8,CH:8,L1:16,DED:9}.
    # L1 cap=16 > 0 → enter L1 regardless of occupancy.
    players = {f"P{i}": {"tier": "PRM"} for i in range(10)}
    players.update({f"C{i}": {"tier": "CH"} for i in range(10)})
    players.update({f"L{i}": {"tier": "L1"} for i in range(20)})
    lb = {"players": players}
    assert detect_entry_tier(lb) == "L1"


def test_detect_entry_tier_21_player_league_returns_l1():
    from game.components.leaderboard import detect_entry_tier

    # Regression: 20-player league at capacity (PRM=6, CH=6, L1=8 per tier_capacities(20)).
    # Old code returned PRM for the 21st player because L1 and CH were "full".
    # Correct behaviour: enter L1 (cap rises to 8 for n=21, still > 0).
    players = {f"P{i}": {"tier": "PRM"} for i in range(6)}
    players.update({f"C{i}": {"tier": "CH"} for i in range(6)})
    players.update({f"L{i}": {"tier": "L1"} for i in range(8)})  # 20 players
    lb = {"players": players}
    assert detect_entry_tier(lb) == "L1"
