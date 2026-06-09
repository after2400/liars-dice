import pytest


@pytest.fixture
def minimal_lb():
    """Two players, both in PRM."""
    return {
        "total_runs": 2,
        "last_updated": "2026-01-01T00:00:00Z",
        "players": {
            "Alice": {
                "display_name": "Alice",
                "github_username": "",
                "date_added": "2026-01-01T00:00:00Z",
                "tier": "PRM",
                "tier_since": "2026-01-01T00:00:00Z",
                "times_inactive": 0,
                "tier_stats": {"PRM": {"wins": 40, "games": 100, "win_pct": 40.0}},
            },
            "Bruno": {
                "display_name": "Bruno",
                "github_username": "",
                "date_added": "2026-01-01T00:00:00Z",
                "tier": "PRM",
                "tier_since": "2026-01-01T00:00:00Z",
                "times_inactive": 0,
                "tier_stats": {"PRM": {"wins": 30, "games": 100, "win_pct": 30.0}},
            },
        },
    }


@pytest.fixture
def full_two_tier_lb():
    """Four players: 2 PRM, 2 CH."""
    return {
        "total_runs": 5,
        "last_updated": "2026-01-01T00:00:00Z",
        "players": {
            "Alice": {
                "display_name": "Alice",
                "github_username": "",
                "date_added": "2026-01-01T00:00:00Z",
                "tier": "PRM",
                "tier_since": "2026-01-01T00:00:00Z",
                "times_inactive": 0,
                "tier_stats": {"PRM": {"wins": 40, "games": 100, "win_pct": 40.0}},
            },
            "Bruno": {
                "display_name": "Bruno",
                "github_username": "",
                "date_added": "2026-01-01T00:00:00Z",
                "tier": "PRM",
                "tier_since": "2026-01-01T00:00:00Z",
                "times_inactive": 0,
                "tier_stats": {"PRM": {"wins": 30, "games": 100, "win_pct": 30.0}},
            },
            "Cleo": {
                "display_name": "Cleo",
                "github_username": "",
                "date_added": "2026-01-01T00:00:00Z",
                "tier": "CH",
                "tier_since": "2026-01-01T00:00:00Z",
                "times_inactive": 0,
                "tier_stats": {"CH": {"wins": 20, "games": 100, "win_pct": 20.0}},
            },
            "Diego": {
                "display_name": "Diego",
                "github_username": "",
                "date_added": "2026-01-01T00:00:00Z",
                "tier": "CH",
                "tier_since": "2026-01-01T00:00:00Z",
                "times_inactive": 0,
                "tier_stats": {"CH": {"wins": 10, "games": 100, "win_pct": 10.0}},
            },
        },
    }


@pytest.fixture
def lb_with_pending():
    """Leaderboard with a pending PRM→CH relegation for Alice."""
    return {
        "total_runs": 3,
        "last_updated": "2026-01-01T00:00:00Z",
        "pending_relegation": [{"player": "Alice", "from_tier": "PRM", "to_tier": "CH"}],
        "players": {
            "Alice": {
                "display_name": "Alice",
                "github_username": "",
                "date_added": "2026-01-01T00:00:00Z",
                "tier": "PRM",
                "tier_since": "2026-01-01T00:00:00Z",
                "times_inactive": 0,
                "tier_stats": {"PRM": {"wins": 40, "games": 100, "win_pct": 40.0}},
            },
            "Bruno": {
                "display_name": "Bruno",
                "github_username": "",
                "date_added": "2026-01-01T00:00:00Z",
                "tier": "PRM",
                "tier_since": "2026-01-01T00:00:00Z",
                "times_inactive": 0,
                "tier_stats": {"PRM": {"wins": 30, "games": 100, "win_pct": 30.0}},
            },
        },
    }


@pytest.fixture
def lb_file(tmp_path, minimal_lb):
    """Write minimal_lb to a temp file and return its path."""
    import yaml

    path = tmp_path / "leaderboard.yaml"
    path.write_text(yaml.dump(minimal_lb, default_flow_style=False, sort_keys=False))
    return str(path)
