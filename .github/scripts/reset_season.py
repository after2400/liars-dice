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

import json
import math
import os
import subprocess
import sys
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path

_SCRIPT_DIR = Path(__file__).parent
_REPO_ROOT = _SCRIPT_DIR.parent.parent

_repo_root_str = str(_REPO_ROOT)
if _repo_root_str not in sys.path:
    sys.path.insert(0, _repo_root_str)

from season_utils import _load_lb, _save_lb  # noqa: E402

_DRY_RUN = os.environ.get("DRY_RUN", "").lower() in ("1", "true", "yes")


def _today() -> date:
    raw = os.environ.get("TODAY")
    if not raw:
        return date.today()
    try:
        return date.fromisoformat(raw)
    except ValueError:
        raise ValueError(f"TODAY env var must be YYYY-MM-DD, got: {raw!r}") from None


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


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


def _run_pool(pool: list[str], n_games: int, lb_path: str) -> dict[str, int]:
    """Run n_games games for the given pool. Returns {class_name: win_count}."""
    with tempfile.NamedTemporaryFile(suffix=".json", prefix="pool_results_", delete=False) as tmp:
        results_file = tmp.name
    try:
        env = {**os.environ, "LEADERBOARD_PATH": lb_path}
        cmd = [
            "uv",
            "run",
            "python",
            "-m",
            "game",
            str(n_games),
            str(len(pool)),
            "--no-game-results",
            "--players",
            *pool,
            "--results-file",
            results_file,
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=str(_REPO_ROOT))
        print(proc.stdout, end="")
        if proc.returncode != 0:
            print(f"[warn] pool game engine exited {proc.returncode}", file=sys.stderr)
            print(proc.stderr, end="", file=sys.stderr)
            return {}
        with open(results_file) as f:
            return json.load(f)
    finally:
        try:
            os.unlink(results_file)
        except FileNotFoundError:
            pass


def run_pools(lb_path: str, n_games: int) -> None:
    """Form pools from current standings and run tournament games. Idempotent.

    Players are seeded by tier order (PRM first → DED last), then by total
    win% descending within each tier. Pools are distributed via S-curve.
    Results stored in tournament_state.pool_results.
    """
    data = _load_lb(lb_path)
    state = data.get("tournament_state") or {}

    if state.get("pool_results"):
        print("[skip] run_pools: pool_results already present")
        return

    from game.components.leaderboard import get_tier_players

    tier_order = ["PRM", "CH", "L1", "DED", "inactive"]
    seeded: list[str] = []
    players_data = data.get("players", {})

    def _win_pct(name: str) -> float:
        ts = players_data[name].get("tier_stats", {})
        total_w = sum(t.get("wins", 0) for t in ts.values())
        total_g = sum(t.get("games", 0) for t in ts.values())
        return total_w / total_g if total_g else 0.0

    for tier in tier_order:
        in_tier = get_tier_players(data, tier)
        in_tier.sort(key=_win_pct, reverse=True)
        seeded.extend(in_tier)

    n_players = len(seeded)
    n_pools = max(1, math.ceil(n_players / 8))
    pools = form_pools(seeded, n_pools)

    pool_results: dict[str, dict[str, int]] = {}
    for i, pool in enumerate(pools):
        key = f"pool_{i}"
        print(f"[run] {key}: {pool}")
        wins = _run_pool(pool, n_games, lb_path)
        pool_results[key] = wins
        print(f"[done] {key}: {wins}")

    state["pool_results"] = pool_results
    data["tournament_state"] = state
    _save_lb(data, lb_path)
    print(f"[done] run_pools: {n_pools} pool(s) complete")


def assign_placements(lb_path: str, n_games: int) -> None:
    """Assign tier placements from pool_results, top-down by win count.

    Always re-derives from pool_results — safe to re-run.
    """
    from game.components.leaderboard import tier_capacities

    data = _load_lb(lb_path)
    state = data.get("tournament_state") or {}
    pool_results = state.get("pool_results", {})

    if not pool_results:
        print(
            "[warn] assign_placements: no pool_results found — run run_pools() first",
            file=sys.stderr,
        )
        return

    # Flatten pool results: {player: total_wins}
    all_wins: dict[str, int] = {}
    for wins in pool_results.values():
        all_wins.update(wins)

    # Rank all players by wins descending
    ranked = [name for name, _ in sorted(all_wins.items(), key=lambda x: -x[1])]

    n_players = len(data.get("players", {}))
    caps = tier_capacities(n_players)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    idx = 0
    players = data.get("players", {})
    for tier in ("PRM", "CH", "L1", "DED"):
        cap = caps.get(tier, 0)
        for _ in range(cap):
            if idx >= len(ranked):
                break
            name = ranked[idx]
            if name in players:
                players[name]["tier"] = tier
                players[name]["tier_since"] = now
            idx += 1

    _save_lb(data, lb_path)
    print(f"[done] assign_placements: {n_players} players placed")


def _gh_create_issue(title: str, repo: str) -> int:
    """Create a GitHub issue and return its number."""
    if _DRY_RUN:
        print(f"[dry-run] would create issue: {title!r} in {repo}")
        return 0
    result = subprocess.run(
        [
            "gh",
            "issue",
            "create",
            "--repo",
            repo,
            "--title",
            title,
            "--body",
            "",
            "--json",
            "number",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"gh issue create failed: {result.stderr}")
    return json.loads(result.stdout)["number"]


def _gh_post_comment(issue_number: int, body_file: str, repo: str) -> None:
    """Post a comment to a GitHub issue from a file."""
    if _DRY_RUN:
        print(f"[dry-run] would post comment to issue #{issue_number} in {repo}")
        return
    result = subprocess.run(
        ["gh", "issue", "comment", str(issue_number), "--repo", repo, "--body-file", body_file],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"[warn] gh issue comment failed: {result.stderr}", file=sys.stderr)


def create_season_issue(lb_path: str, quarter: str, summary_file: str) -> None:
    """Create the quarter's tracking issue and post tournament summary. Idempotent."""
    data = _load_lb(lb_path)
    state = data.get("tournament_state") or {}

    if state.get("issue_created"):
        print(f"[skip] create_season_issue: already created for {quarter}")
        return

    repo = os.environ.get("GH_REPO", "")
    if not repo:
        print("[warn] GH_REPO not set — skipping issue creation", file=sys.stderr)
        return

    title = f"{quarter} Season"
    issue_number = _gh_create_issue(title, repo)
    print(f"[done] Created issue #{issue_number}: {title}")

    if os.path.exists(summary_file):
        _gh_post_comment(issue_number, summary_file, repo)
        print(f"[done] Posted tournament summary to #{issue_number}")
    else:
        print(
            f"[warn] summary_file not found — skipping comment on #{issue_number}", file=sys.stderr
        )

    if not _DRY_RUN:
        data["current_season_issue"] = issue_number
        state["issue_created"] = True
        data["tournament_state"] = state
        _save_lb(data, lb_path)
        print(f"[done] current_season_issue set to {issue_number}")


def _write_tournament_summary(summary_file: str, lb_path: str, quarter: str) -> None:
    """Write a markdown summary of tournament results."""
    from game.components.leaderboard import build_display_names

    data = _load_lb(lb_path)
    state = data.get("tournament_state") or {}
    pool_results = state.get("pool_results", {})
    players = data.get("players", {})

    display_names = build_display_names(players)

    lines = [f"# Tournament Summary — {quarter}", ""]

    lines += ["## Tier Placements", ""]
    for tier in ("PRM", "CH", "L1", "DED"):
        in_tier = [n for n, p in players.items() if p.get("tier") == tier]
        if in_tier:
            label = {
                "PRM": "Premier",
                "CH": "Championship",
                "L1": "League One",
                "DED": "Dead Letter",
            }.get(tier, tier)

            def _q(name: str) -> str:
                return f'"{name}"' if "," in name else name

            lines.append(f"**{label}:** " + ", ".join(_q(display_names.get(n, n)) for n in in_tier))
    lines.append("")

    if pool_results:
        lines += ["## Pool Results", ""]
        for pool_key, wins in pool_results.items():
            lines.append(f"### {pool_key.replace('_', ' ').title()}")
            lines.append("| Player | Wins |")
            lines.append("|--------|------|")
            for name, w in sorted(wins.items(), key=lambda x: -x[1]):
                lines.append(f"| {display_names.get(name, name)} | {w} |")
            lines.append("")

    with open(summary_file, "w") as f:
        f.write("\n".join(lines))


def main() -> None:
    n_games = int(os.environ.get("N_GAMES", "1000"))
    lb_path = os.environ.get("LEADERBOARD_PATH", "leaderboard.yaml")
    summary_file = os.environ.get("SUMMARY_FILE", "season_summary.md")

    quarter = current_quarter()
    print(f"[reset_season] quarter={quarter} n_games={n_games} lb={lb_path}")

    zero_stats(lb_path, quarter=quarter)
    run_pools(lb_path, n_games=n_games)
    assign_placements(lb_path, n_games=n_games)
    _write_tournament_summary(summary_file, lb_path, quarter)
    print(open(summary_file).read())
    create_season_issue(lb_path, quarter=quarter, summary_file=summary_file)
    print("[done] Quarterly reset complete.")


if __name__ == "__main__":
    main()
