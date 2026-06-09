import os
from datetime import datetime, timezone

import yaml

_LEADERBOARD_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "leaderboard.yaml")
)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def apply_pending_relegation(data: dict) -> dict:
    """Apply all pending_relegation entries and clear the list. Returns updated data."""
    now = _now()
    for entry in data.get("pending_relegation", []):
        player = entry["player"]
        new_tier = entry["to_tier"]
        if player in data.get("players", {}):
            data["players"][player]["tier"] = new_tier
            data["players"][player]["tier_since"] = now
    data["pending_relegation"] = []
    return data


def detect_phase(data: dict, top_n: int) -> int:
    """Return 1, 2, or 3 based on total player count relative to TOP_N.

    Inactive players are counted — phase reflects system capacity, not active rosters.
    """
    total = len(data.get("players", {}))
    if total <= top_n:
        return 1
    if total <= top_n * 2:
        return 2
    return 3


def get_tier_players(data: dict, tier: str) -> list[str]:
    """Return player names whose tier matches the given value."""
    return [name for name, p in data.get("players", {}).items() if p.get("tier") == tier]


def update_leaderboard(
    wins: dict[str, int],
    n_games: int,
    tier: str,
    promotions: dict[str, str] | None = None,
    pending_relegations: list[dict] | None = None,
    last_place: str | None = None,
    path: str = _LEADERBOARD_PATH,
) -> None:
    """
    Update cumulative stats for players who competed, apply tier changes,
    append deferred relegations, and write leaderboard.yaml.

    Args:
        wins: {player_name: win_count} for this run only.
        n_games: games played this run.
        tier: which league ran ('PRM', 'CH', 'L1').
        promotions: {player_name: new_tier} — applied immediately.
        pending_relegations: list of {player, from_tier, to_tier} — deferred.
        last_place: player who finished last (increments times_last_in_l1 if tier=='L1').
        path: path to leaderboard.yaml.
    """
    promotions = promotions or {}
    pending_relegations = pending_relegations or []

    if os.path.exists(path):
        with open(path) as f:
            data = yaml.safe_load(f) or {}
    else:
        data = {}

    now = _now()
    data.setdefault("total_runs", 0)
    data["total_runs"] += 1
    data["last_updated"] = now
    data.setdefault("players", {})
    data.setdefault("pending_relegation", [])

    # Update stats for competing players; create entry for new players
    for name, win_count in wins.items():
        player = data["players"].setdefault(
            name,
            {
                "display_name": name,
                "github_username": "",
                "date_added": now,
                "tier": tier,
                "tier_since": now,
                "times_inactive": 0,
                "tier_stats": {},
            },
        )
        ts = player.setdefault("tier_stats", {})
        ts_tier = ts.setdefault(tier, {"wins": 0, "games": 0, "win_pct": 0.0})
        ts_tier["wins"] += win_count
        ts_tier["games"] += n_games
        ts_tier["win_pct"] = round(ts_tier["wins"] / ts_tier["games"] * 100, 1)

    # Apply immediate promotions (tier changes now)
    for name, new_tier in promotions.items():
        if name in data["players"]:
            if data["players"][name]["tier"] != new_tier:
                data["players"][name]["tier"] = new_tier
                data["players"][name]["tier_since"] = now

    # Append deferred relegations
    data["pending_relegation"].extend(pending_relegations)

    # Increment times_inactive for last place in L1 runs
    if tier == "L1" and last_place and last_place in data["players"]:
        data["players"][last_place]["times_inactive"] = (
            data["players"][last_place].get("times_inactive", 0) + 1
        )

    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)


_TIER_ABOVE = {"L1": "CH", "CH": "PRM", "inactive": "L1"}
_TIER_BELOW = {"PRM": "CH", "CH": "L1", "L1": "inactive"}


def _TIER_CAPACITY(tier: str, top_n: int) -> float:
    if tier in ("PRM", "CH"):
        return top_n
    if tier == "L1":
        return top_n * 2
    return float("inf")


def apply_season_results(
    wins: dict[str, int],
    n_games: int,
    tier: str,
    top_n: int,
    path: str = _LEADERBOARD_PATH,
) -> None:
    """Update stats and apply immediate promotions/relegations for a scheduled run."""
    if os.path.exists(path):
        with open(path) as f:
            data = yaml.safe_load(f) or {}
    else:
        data = {}

    now = _now()
    data.setdefault("total_runs", 0)
    data["total_runs"] += 1
    data["last_updated"] = now
    data.setdefault("players", {})

    # Update cumulative tier_stats for competing players
    for name, win_count in wins.items():
        if name not in data["players"]:
            continue
        player = data["players"][name]
        ts = player.setdefault("tier_stats", {})
        ts_tier = ts.setdefault(tier, {"wins": 0, "games": 0, "win_pct": 0.0})
        ts_tier["wins"] += win_count
        ts_tier["games"] += n_games
        ts_tier["win_pct"] = round(ts_tier["wins"] / ts_tier["games"] * 100, 1)

    # Rank by wins desc; tiebreak on historical tier games desc, then tier_since asc
    def _rank_key(item):
        name, w = item
        p = data["players"].get(name, {})
        tier_games = p.get("tier_stats", {}).get(tier, {}).get("games", 0)
        return (-w, -tier_games, p.get("tier_since", ""))

    ranked = sorted(wins.items(), key=_rank_key)
    players_in_tier = [name for name, _ in ranked if name in data["players"]]

    tier_above = _TIER_ABOVE.get(tier)
    tier_below = _TIER_BELOW.get(tier)

    # Promote top player unconditionally
    promoted = None
    if tier_above and players_in_tier:
        promoted = players_in_tier[0]
        data["players"][promoted]["tier"] = tier_above
        data["players"][promoted]["tier_since"] = now

    # Relegate enough from the bottom to restore this tier to capacity.
    # If a promotion occurred, relegate only the excess; otherwise always relegate at least 1.
    if tier_below:
        capacity = _TIER_CAPACITY(tier, top_n)
        remaining = [p for p in players_in_tier if p != promoted]
        if promoted:
            excess = max(0, len(remaining) - capacity) if remaining else 0
        else:
            excess = max(1, len(remaining) - capacity) if remaining else 0
        for name in reversed(remaining):
            if excess <= 0:
                break
            data["players"][name]["tier"] = tier_below
            data["players"][name]["tier_since"] = now
            if tier_below == "inactive":
                data["players"][name]["times_inactive"] = (
                    data["players"][name].get("times_inactive", 0) + 1
                )
            excess -= 1

    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)
