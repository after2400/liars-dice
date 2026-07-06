#!/usr/bin/env python3
"""Daily season driver — runs all tier games bottom-up and updates the leaderboard.

Environment variables:
  N_GAMES           games per tier (default 250)
  TOP_N             league capacity per tier (default 4)
  LEADERBOARD_PATH  path to leaderboard.yaml (default leaderboard.yaml)
  SUMMARY_FILE      path to write season summary markdown (default season_summary.md)

Tiers run bottom-up: inactive → L1 → CH → PRM.
A tier is skipped when it has fewer than 2 players.
After each tier runs, apply_season_results() is called immediately so
promotions/relegations are in effect before the next tier above starts.
"""

import inspect
import math
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Project root: two levels above this script (.github/scripts/run_season.py)
# Ensure it's on sys.path so `game` is importable when script is run directly.
# ---------------------------------------------------------------------------
_SCRIPT_DIR = Path(__file__).parent
_REPO_ROOT = _SCRIPT_DIR.parent.parent

_repo_root_str = str(_REPO_ROOT)
if _repo_root_str not in sys.path:
    sys.path.insert(0, _repo_root_str)

from game.season.utils import (  # noqa: E402
    _TIER_LABEL,
    _load_lb,
    _quarter_leaderboard_table,  # noqa: F401
    _standings_table,  # noqa: F401
    _update_readme,
    expel_player,
    form_pools,
    run_game_with_retry,
)

_DRY_RUN = os.environ.get("DRY_RUN", "").lower() in ("1", "true", "yes")
_POOL_MAX = 9  # maximum players per L1 pool; split when L1 exceeds this


def _get_tier_players(data: dict, tier: str) -> list[str]:
    """Return class names whose current tier matches *tier*."""
    return [name for name, p in data.get("players", {}).items() if p.get("tier") == tier]


def _run_tier(
    tier: str, n_games: int, top_n: int, lb_path: str
) -> tuple[dict[str, int], list[str]]:
    """Run python -m game for *tier*.

    Returns (wins, offenders): wins is {} if unrecoverable (after a
    retry-without-offender attempt, if a security violation triggered it —
    see run_game_with_retry). The caller must expel each offender itself,
    once lb_path is writable again — run_season() chmods it read-only for
    the duration of each tier's game-running call.
    """
    env = {**os.environ, "LEADERBOARD_PATH": lb_path}
    base_cmd = [
        "uv",
        "run",
        "python",
        "-m",
        "game",
        str(n_games),
        str(top_n),
        "--tier",
        tier,
    ]
    return run_game_with_retry(base_cmd, env, _REPO_ROOT, warn_label=f" for tier {tier}")


def _run_players(
    players: list[str], n_games: int, lb_path: str
) -> tuple[dict[str, int], list[str]]:
    """Run n_games for a specific player list.

    Returns (wins, offenders) — see _run_tier docstring; the caller must
    expel each offender itself once lb_path is writable again.
    """
    env = {**os.environ, "LEADERBOARD_PATH": lb_path}
    base_cmd = [
        "uv",
        "run",
        "python",
        "-m",
        "game",
        str(n_games),
        str(len(players)),
        "--no-game-results",
        "--players",
        *players,
    ]
    return run_game_with_retry(base_cmd, env, _REPO_ROOT)


def _scan_v1_players(lb_path: str) -> list[str]:
    """Return display names of registered players still on the v1 algo() interface."""
    import importlib.util

    from game.components.leaderboard import build_display_names

    data = _load_lb(lb_path)
    players_data = data.get("players", {})
    display_names = build_display_names(players_data)

    players_dir = _REPO_ROOT / "players"
    v1: list[str] = []

    for class_name in players_data:
        player_file = players_dir / f"{class_name.lower()}.py"
        if not player_file.exists():
            continue
        spec = importlib.util.spec_from_file_location(class_name.lower(), player_file)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        cls = getattr(module, class_name, None)
        if cls is None:
            continue
        params = inspect.signature(cls().algo).parameters
        positional = sum(
            1
            for name, param in params.items()
            if name != "self"
            and param.kind
            in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
            )
        )
        if positional != 1:
            v1.append(display_names.get(class_name, class_name))

    return sorted(v1)


def run_season(
    n_games: int,
    top_n: int,
    lb_path: str,
    summary_file: str,
    readme_path: str = str(_REPO_ROOT / "README.md"),
) -> None:
    """Orchestrate a full bottom-up season run and write a markdown summary."""
    from game.components.leaderboard import apply_season_results, settle_relegations

    v1_players = _scan_v1_players(lb_path)
    if v1_players:
        print(f"[warn] v1 algo() players ({len(v1_players)}): {', '.join(v1_players)}")

    tier_order = ["inactive", "L1", "CH", "PRM"]
    skipped: list[str] = []
    # Store per-tier results for the summary: tier → wins dict
    tier_results: dict[str, dict[str, int]] = {}

    for tier in tier_order:
        data = _load_lb(lb_path)
        players_in_tier = _get_tier_players(data, tier)

        if len(players_in_tier) < 2:
            print(f"[skip] {tier}: {len(players_in_tier)} player(s) — need ≥ 2 to run games.")
            skipped.append(tier)
            continue

        if tier == "L1" and len(players_in_tier) > _POOL_MAX:
            n_pools = math.ceil(len(players_in_tier) / _POOL_MAX)
            seeded = sorted(
                players_in_tier,
                key=lambda n: (
                    -data["players"][n].get("tier_stats", {}).get("L1", {}).get("win_pct", 0.0)
                ),
            )
            pools = form_pools(seeded, n_pools)
            print(
                f"[run] {tier}: {len(players_in_tier)} players → "
                f"{n_pools} pools of ≤{_POOL_MAX}, {n_games} games each …"
            )
            wins: dict[str, int] = {}
            offenders: list[str] = []
            try:
                os.chmod(lb_path, 0o444)
                for i, pool in enumerate(pools):
                    print(f"  [pool {i + 1}/{n_pools}]: {pool}")
                    pool_wins, pool_offenders = _run_players(pool, n_games, lb_path)
                    wins.update(pool_wins)
                    offenders.extend(pool_offenders)
            finally:
                os.chmod(lb_path, 0o644)
        else:
            print(f"[run] {tier}: {len(players_in_tier)} players, {n_games} games each …")
            try:
                os.chmod(lb_path, 0o444)
                wins, offenders = _run_tier(tier, n_games, top_n, lb_path)
            finally:
                os.chmod(lb_path, 0o644)

        for offender in offenders:
            expel_player(lb_path, offender, _REPO_ROOT, _DRY_RUN)

        if not wins:
            print(f"[skip] {tier}: game engine returned no results.")
            skipped.append(tier)
            continue

        tier_results[tier] = wins
        movements = apply_season_results(wins, n_games, tier, top_n, path=lb_path)
        for m in movements:
            print(f"  {m}")
        print(f"[done] {tier}: leaderboard updated.")

    relegations = settle_relegations(tier_results, top_n, path=lb_path)
    if relegations:
        print("[settle] cross-tier relegations:")
        for m in relegations:
            print(f"  {m}")

    _write_summary(summary_file, tier_results, skipped, n_games, lb_path, v1_players)
    print(f"[done] Season summary written to {summary_file}")
    _update_readme(readme_path, lb_path, tier_results, n_games, dry_run=_DRY_RUN)
    print(
        "[done] README standings updated."
        if not _DRY_RUN
        else "[dry-run] would update README standings."
    )
    _post_season_from_lb(lb_path, summary_file)
    print("[done] Season summary posted to tracking issue.")


def _write_summary(
    summary_file: str,
    tier_results: dict[str, dict[str, int]],
    skipped: list[str],
    n_games: int,
    lb_path: str,
    v1_players: list[str] | None = None,
) -> None:
    """Write a markdown season summary: final standings + collapsed per-tier game results."""
    from game.components.leaderboard import build_display_names

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    data = _load_lb(lb_path)
    players = data.get("players", {})
    display_names = build_display_names(players)

    lines: list[str] = [f"# Season Summary — {today}", ""]

    # --- Final standings (post-run leaderboard state, mirrors README) ---
    lines.append("## Final Standings")
    lines.append("")

    for tier in ("PRM", "CH", "L1"):
        label = _TIER_LABEL[tier]
        tier_players = [(n, p) for n, p in players.items() if p.get("tier") == tier]
        tier_players.sort(
            key=lambda x: -x[1].get("tier_stats", {}).get(tier, {}).get("win_pct", 0.0)
        )
        lines.append(f"### {label}")
        if tier_players:
            lines.extend(_standings_table(tier_players, tier, display_names, tier_results, n_games))
        else:
            lines.append(f"*No players currently in {label}.*")
        lines.append("")

    inactive_players = [(n, p) for n, p in players.items() if p.get("tier") == "inactive"]
    if inactive_players:

        def _q(s: str) -> str:
            return f'"{s}"' if "," in s else s

        names = ", ".join(_q(display_names.get(n, n)) for n, _ in inactive_players)
        lines.append(f"*Inactive: {names}*")
        lines.append("")

    # --- Per-tier game results (collapsed) ---
    ran_tiers = [t for t in ("PRM", "CH", "L1", "inactive") if t in tier_results]
    if ran_tiers:
        lines.append("---")
        lines.append("")
        lines.append("## Game Results")
        lines.append("")

        for i, tier in enumerate(ran_tiers):
            if i > 0:
                lines.append("---")
                lines.append("")

            wins = tier_results[tier]
            label = _TIER_LABEL.get(tier, tier)
            lines.append("<details>")
            lines.append(f"<summary>{label} — {n_games} games</summary>")
            lines.append("")
            lines.append("| Player | Wins | Win % |")
            lines.append("|--------|------|-------|")

            for class_name, win_count in sorted(wins.items(), key=lambda x: -x[1]):
                display = display_names.get(class_name, class_name)
                win_pct = round(win_count / n_games * 100, 1) if n_games else 0.0
                lines.append(f"| {display} | {win_count} | {win_pct}% |")

            lines.append("")
            lines.append("</details>")
            lines.append("")

            movements = []
            for class_name in wins:
                p = players.get(class_name, {})
                current_tier = p.get("tier", tier)
                display = display_names.get(class_name, class_name)
                if current_tier != tier:
                    direction = (
                        "Promoted" if _tier_rank(current_tier) > _tier_rank(tier) else "Relegated"
                    )
                    movements.append(f"{direction}: {display} → {current_tier}")
            for m in movements:
                lines.append(m)
            if movements:
                lines.append("")

    if skipped:
        skipped_str = ", ".join(f"{t} (< 2 players)" for t in skipped)
        lines.append(f"*Skipped: {skipped_str}*")
        lines.append("")

    if v1_players:
        lines.append("---")
        lines.append("")
        lines.append("## Migrate to v2 before 2026-10-05")
        lines.append("")
        lines.append(
            "The following players are still using the deprecated `algo(self, hand, prior_bet, ...)` "
            "interface and will be dropped from the league on the cutover date:"
        )
        lines.append("")
        for name in v1_players:
            lines.append(f"- {name}")
        lines.append("")
        lines.append(
            "See the [Player Guide](https://github.com/after2400/liars-dice/wiki/Player-Guide) "
            "for migration instructions."
        )
        lines.append("")

    with open(summary_file, "w") as f:
        f.write("\n".join(lines))


def _tier_rank(tier: str) -> int:
    """Higher number = higher tier."""
    return {"inactive": 0, "L1": 1, "CH": 2, "PRM": 3}.get(tier, -1)


def _post_season_summary(issue_number: int, summary_file: str) -> None:
    """Post the season summary markdown to the given GitHub issue."""
    if _DRY_RUN:
        print(f"[dry-run] would post summary to issue #{issue_number}")
        return
    result = subprocess.run(
        ["gh", "issue", "comment", str(issue_number), "--body-file", summary_file],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"[warn] gh issue comment failed: {result.stderr}", file=sys.stderr)


def _post_season_from_lb(lb_path: str, summary_file: str) -> None:
    """Read current_season_issue from leaderboard.yaml and post the summary."""
    data = _load_lb(lb_path)
    issue_number = data.get("current_season_issue")
    if issue_number is None:
        print(
            "[warn] current_season_issue not set in leaderboard.yaml — skipping post",
            file=sys.stderr,
        )
        return
    _post_season_summary(int(issue_number), summary_file)


def main() -> None:
    n_games = int(os.environ.get("N_GAMES", "1000"))
    top_n = int(os.environ.get("TOP_N", "4"))
    lb_path = os.environ.get("LEADERBOARD_PATH", "leaderboard.yaml")
    summary_file = os.environ.get("SUMMARY_FILE", "season_summary.md")
    readme_path = os.environ.get("README_PATH", str(_REPO_ROOT / "README.md"))

    print(f"[run_season] n_games={n_games} top_n={top_n} lb={lb_path} summary={summary_file}")
    run_season(n_games, top_n, lb_path, summary_file, readme_path)


if __name__ == "__main__":
    main()
