import os
from collections import defaultdict
from datetime import datetime, timezone

import yaml

_LEADERBOARD_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "leaderboard.yaml")
)


def build_display_names(players: dict) -> dict[str, str]:
    """Map each class name (leaderboard key) to its render string.

    A name is suffixed only when 2+ players share the same display_name. The
    suffix is the github_username when it is non-empty AND unique within the
    colliding group; otherwise it falls back to the class name, which is always
    unique. Unique names render bare.
    """
    _ctrl = str.maketrans("", "", "".join(chr(i) for i in range(32)))

    def _clean(s: str) -> str:
        return s.translate(_ctrl).strip()

    names = {cn: _clean(p.get("display_name", cn)) for cn, p in players.items()}

    groups: dict[str, list[str]] = defaultdict(list)
    for cn, name in names.items():
        groups[name].append(cn)

    result: dict[str, str] = {}
    for cn, name in names.items():
        if len(groups[name]) <= 1:
            result[cn] = name
            continue
        username = players[cn].get("github_username") or ""
        same_username_count = sum(
            (players[s].get("github_username") or "") == username for s in groups[name]
        )
        username_unique = bool(username) and same_username_count == 1
        result[cn] = f"{name} ({username if username_unique else cn})"
    return result


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get_tier_players(data: dict, tier: str) -> list[str]:
    """Return player names whose tier matches the given value."""
    return [name for name, p in data.get("players", {}).items() if p.get("tier") == tier]


_TIER_ABOVE = {"L1": "CH", "CH": "PRM", "inactive": "L1"}
_TIER_BELOW = {"PRM": "CH", "CH": "L1", "L1": "inactive"}


def tier_capacities(n_players: int) -> dict[str, int]:
    """Return target capacity per tier for n_players total registered players."""
    if n_players <= 16:
        return {"PRM": 4, "CH": 4, "L1": max(0, n_players - 8), "DED": 0}
    if n_players <= 24:
        extra = n_players - 16  # 1..8: PRM grows first, then CH alternates
        return {"PRM": 4 + (extra + 1) // 2, "CH": 4 + extra // 2, "L1": 8, "DED": 0}
    if n_players <= 32:
        return {"PRM": 8, "CH": 8, "L1": 8 + (n_players - 24), "DED": 0}
    return {"PRM": 8, "CH": 8, "L1": 16, "DED": n_players - 32}


def detect_entry_tier(lb: dict) -> str:
    """Return the entry tier for a new player: always the lowest tier that exists.

    Current occupancy is intentionally ignored — a temporarily over-capacity L1
    is fine; the next season run promotes/relegates to restore balance. New players
    should never skip directly to CH or PRM because a higher tier has a free slot.
    """
    players = lb.get("players", {})
    n_after = len(players) + 1
    caps = tier_capacities(n_after)
    if caps.get("L1", 0) > 0:
        return "L1"
    for tier in ("CH", "PRM"):
        if caps.get(tier, 0) > 0:
            return tier
    return "DED"


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
) -> list[str]:
    """Update stats and apply the immediate promotion for a scheduled run."""
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

    movements: list[str] = []

    display_names = build_display_names(data["players"])

    def _display(name: str) -> str:
        return display_names.get(name, name)

    # Promote top player unconditionally
    if tier_above and players_in_tier:
        promoted = players_in_tier[0]
        data["players"][promoted]["tier"] = tier_above
        data["players"][promoted]["tier_since"] = now
        movements.append(f"Promoted: {_display(promoted)} → {tier_above}")

    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    return movements


def settle_relegations(
    tier_results: dict[str, dict[str, int]],
    top_n: int,
    path: str = _LEADERBOARD_PATH,
) -> list[str]:
    """Top-down relegation settlement, run once after a full bottom-up season.

    Walks PRM → CH → L1. Each tier sheds its excess over capacity into the tier
    below, choosing the worst performers who actually PLAYED that tier this run.
    A player relegated into a tier during this pass (a "parachutist") holds a
    protected seat and is not re-relegated the same night.

    tier_results: {tier: {player: win_count}} for this run's games — used to
        rank who played worst in each tier.
    Returns "Relegated: <name> → <tier>" movement strings, in cascade order.
    """
    if os.path.exists(path):
        with open(path) as f:
            data = yaml.safe_load(f) or {}
    else:
        data = {}

    now = _now()
    data.setdefault("players", {})
    data["last_updated"] = now
    players = data["players"]
    display_names = build_display_names(players)

    parachutists: dict[str, set[str]] = {}
    movements: list[str] = []

    for tier in ("PRM", "CH", "L1"):
        tier_below = _TIER_BELOW.get(tier)
        if tier_below is None:
            continue
        capacity = max(
            tier_capacities(len(players)).get(tier, 0),
            _TIER_CAPACITY(tier, top_n),
        )
        residents = [n for n, p in players.items() if p.get("tier") == tier]
        excess = len(residents) - capacity
        if excess <= 0:
            continue

        protected = parachutists.get(tier, set())
        this_season = tier_results.get(tier, {})
        candidates = [n for n in residents if n in this_season and n not in protected]

        # Worst-first ordering. Python's sort is stable, so sort by the
        # least-significant key first: tier_since DESC (newest first), then by
        # (this-season wins ASC, total tier games ASC).
        candidates.sort(key=lambda n: players[n].get("tier_since", ""), reverse=True)
        candidates.sort(
            key=lambda n: (
                this_season[n],
                players[n].get("tier_stats", {}).get(tier, {}).get("games", 0),
            )
        )

        assert len(candidates) >= excess, (
            f"{tier} over capacity by {excess} but only {len(candidates)} "
            f"relegation candidate(s) — upstream invariant broken"
        )

        for name in candidates[:excess]:
            players[name]["tier"] = tier_below
            players[name]["tier_since"] = now
            if tier_below == "inactive":
                players[name]["times_inactive"] = players[name].get("times_inactive", 0) + 1
            parachutists.setdefault(tier_below, set()).add(name)
            movements.append(f"Relegated: {display_names.get(name, name)} → {tier_below}")

    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    return movements
