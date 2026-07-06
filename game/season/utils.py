"""Shared utilities for season scripts."""

import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import yaml


def _load_lb(path: str) -> dict:
    if os.path.exists(path):
        with open(path) as f:
            return yaml.safe_load(f) or {}
    return {}


def _save_lb(data: dict, path: str) -> None:
    data["last_updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)


def _today() -> date:
    raw = os.environ.get("TODAY")
    if not raw:
        return date.today()
    try:
        return date.fromisoformat(raw)
    except ValueError:
        raise ValueError(f"TODAY env var must be YYYY-MM-DD, got: {raw!r}") from None


def current_quarter(today: date | None = None) -> str:
    """Return e.g. '2026-Q3' for the quarter containing today."""
    d = today or _today()
    q = (d.month - 1) // 3 + 1
    return f"{d.year}-Q{q}"


def is_tournament_monday(today: date | None = None) -> bool:
    """Return True if today is the first Monday of a new quarter."""
    d = today or _today()
    if d.weekday() != 0:  # 0 = Monday
        return False
    return d.month in (1, 4, 7, 10) and d.day <= 7


def next_tournament_monday(today: date | None = None) -> date:
    """Return the next date that is a tournament Monday (on or after today)."""
    d = today or _today()
    for i in range(100):
        candidate = d + timedelta(days=i)
        if is_tournament_monday(candidate):
            return candidate
    raise ValueError("No tournament Monday found in next 100 days")


def expel_player(lb_path: str, class_name: str, repo_root: Path, dry_run: bool = False) -> None:
    """Permanently remove a player from the league and delete their source file.

    Shared by run_season.py (regular Monday tiers) and reset_season.py
    (quarterly tournament pools) so a security-violation offender is handled
    identically regardless of which driver caught it.

    Refuses to touch anything unless *dry_run* is False AND *lb_path*
    resolves to repo_root/leaderboard.yaml (the real, live leaderboard):

    - Tests always pass an isolated tmp/copy path, which never resolves to
      repo_root/leaderboard.yaml, so the path check alone stops them.
    - Local `just simulate-*` commands set dry_run=True but do NOT override
      the leaderboard path — they intentionally mutate the real
      leaderboard.yaml in place (see CLAUDE.md) — so dry_run is checked
      independently of the path, or a local simulation that catches a
      cheater would delete the real players/*.py source file (`just clean`
      restores leaderboard.yaml, but not a deleted player file).
    """
    if dry_run:
        print(
            f"[SECURITY] {class_name} triggered a security violation, but this is a "
            "dry run — skipping expulsion (local simulation).",
            file=sys.stderr,
        )
        return

    real_lb_path = (repo_root / "leaderboard.yaml").resolve()
    if Path(lb_path).resolve() != real_lb_path:
        print(
            f"[SECURITY] {class_name} triggered a security violation, but {lb_path} "
            "is not the live leaderboard — skipping expulsion (test isolation).",
            file=sys.stderr,
        )
        return

    data = _load_lb(lb_path)
    if class_name in data.get("players", {}):
        del data["players"][class_name]
        _save_lb(data, lb_path)
        print(f"[SECURITY] Expelled {class_name} from league.")

    player_file = repo_root / "players" / f"{class_name.lower()}.py"
    if player_file.exists():
        player_file.unlink()
        print(f"[SECURITY] Deleted {player_file}")


def form_pools(players: list[str], n_pools: int) -> list[list[str]]:
    """Distribute seeded players into n_pools via S-curve (serpentine) seeding.

    Players must be pre-sorted strongest-first. S-curve ensures each pool
    gets one player from every strength band.
    """
    pools: list[list[str]] = [[] for _ in range(n_pools)]
    direction = 1
    pool_idx = 0
    for player in players:
        pools[pool_idx].append(player)
        if direction == 1:
            if pool_idx == n_pools - 1:
                direction = -1
            else:
                pool_idx += 1
        else:
            if pool_idx == 0:
                direction = 1
            else:
                pool_idx -= 1
    return pools
