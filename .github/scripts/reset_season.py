#!/usr/bin/env python3
"""Quarterly season reset — runs the tournament and re-seeds all tiers.

Run conditions (handled by run-monday.yml):
  - First Monday of a new quarter (automatic)
  - Any Monday when force_tournament=true is passed to the workflow

Idempotency: progress is tracked in leaderboard.yaml under `tournament_state`.
Re-running after a failure resumes from the last completed step.

Environment variables:
  N_GAMES           games per pool (default 1000)
  LEADERBOARD_PATH  path to leaderboard.yaml (default leaderboard.yaml)
  SUMMARY_FILE      path to write tournament summary markdown (default season_summary.md)
  GH_TOKEN          GitHub token for issue creation (required in CI)
  GH_REPO           GitHub repo in owner/repo format (required in CI)
"""

import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import yaml

_SCRIPT_DIR = Path(__file__).parent
_REPO_ROOT = _SCRIPT_DIR.parent.parent

_repo_root_str = str(_REPO_ROOT)
if _repo_root_str not in sys.path:
    sys.path.insert(0, _repo_root_str)


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def current_quarter(today: date | None = None) -> str:
    """Return e.g. '2026-Q3' for the quarter containing today."""
    d = today or date.today()
    q = (d.month - 1) // 3 + 1
    return f"{d.year}-Q{q}"


def is_tournament_monday(today: date | None = None) -> bool:
    """Return True if today is the first Monday of a new quarter."""
    d = today or date.today()
    if d.weekday() != 0:  # 0 = Monday
        return False
    return d.month in (1, 4, 7, 10) and d.day <= 7


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


def _load_lb(path: str) -> dict:
    if os.path.exists(path):
        with open(path) as f:
            return yaml.safe_load(f) or {}
    return {}


def _save_lb(data: dict, path: str) -> None:
    data["last_updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)


def zero_stats(lb_path: str, quarter: str) -> None:
    """Zero all tier_stats and mark the tournament quarter. Idempotent.

    If tournament_state.quarter already matches quarter, this is a no-op.
    """
    data = _load_lb(lb_path)
    state = data.get("tournament_state") or {}
    if state.get("quarter") == quarter:
        print(f"[skip] zero_stats: already zeroed for {quarter}")
        return

    for player in data.get("players", {}).values():
        player["tier_stats"] = {}

    state["quarter"] = quarter
    data["tournament_state"] = state
    _save_lb(data, lb_path)
    print(f"[done] zero_stats: all tier_stats cleared for {quarter}")
