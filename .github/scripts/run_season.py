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

import json
import os
import subprocess
import sys
import tempfile
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

import yaml  # noqa: E402


def _load_lb(path: str) -> dict:
    if os.path.exists(path):
        with open(path) as f:
            return yaml.safe_load(f) or {}
    return {}


def _get_tier_players(data: dict, tier: str) -> list[str]:
    """Return class names whose current tier matches *tier*."""
    return [name for name, p in data.get("players", {}).items() if p.get("tier") == tier]


def _run_tier(tier: str, n_games: int, top_n: int, lb_path: str) -> dict[str, int]:
    """Run python -m game for *tier* and return a wins dict {class_name: win_count}.

    Returns an empty dict if the game engine exits with a non-zero status.
    """
    with tempfile.NamedTemporaryFile(
        suffix=".json", prefix=f"{tier}_results_", delete=False
    ) as tmp:
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
            str(top_n),
            "--tier",
            tier,
            "--results-file",
            results_file,
        ]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=env,
            cwd=str(_REPO_ROOT),
        )
        print(proc.stdout, end="")
        if proc.returncode != 0:
            print(f"[warn] game engine exited {proc.returncode} for tier {tier}", file=sys.stderr)
            print(proc.stderr, end="", file=sys.stderr)
            return {}

        with open(results_file) as f:
            wins: dict[str, int] = json.load(f)
        return wins
    finally:
        try:
            os.unlink(results_file)
        except FileNotFoundError:
            pass


def run_season(
    n_games: int,
    top_n: int,
    lb_path: str,
    summary_file: str,
    readme_path: str = str(_REPO_ROOT / "README.md"),
) -> None:
    """Orchestrate a full bottom-up season run and write a markdown summary."""
    from game.components.leaderboard import apply_season_results

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

        print(f"[run] {tier}: {len(players_in_tier)} players, {n_games} games each …")
        wins = _run_tier(tier, n_games, top_n, lb_path)

        if not wins:
            print(f"[skip] {tier}: game engine returned no results.")
            skipped.append(tier)
            continue

        tier_results[tier] = wins
        apply_season_results(wins, n_games, tier, top_n, path=lb_path)
        print(f"[done] {tier}: leaderboard updated.")

    _write_summary(summary_file, tier_results, skipped, n_games, lb_path)
    print(f"[done] Season summary written to {summary_file}")
    _update_readme(readme_path, lb_path)
    print("[done] README standings updated.")


def _write_summary(
    summary_file: str,
    tier_results: dict[str, dict[str, int]],
    skipped: list[str],
    n_games: int,
    lb_path: str,
) -> None:
    """Write a markdown season summary."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    data = _load_lb(lb_path)
    players = data.get("players", {})

    lines: list[str] = [f"# Season Summary — {today}", ""]

    tier_display_order = ["PRM", "CH", "L1", "inactive"]

    for tier in tier_display_order:
        if tier in skipped:
            continue
        wins = tier_results.get(tier)
        if wins is None:
            continue

        lines.append(f"## {tier}")
        lines.append("")
        lines.append("| Player | Wins | Games | Win% |")
        lines.append("|--------|------|-------|------|")

        # Sort by wins descending
        for class_name, win_count in sorted(wins.items(), key=lambda x: -x[1]):
            p = players.get(class_name, {})
            display = p.get("display_name", class_name)
            ts = p.get("tier_stats", {}).get(tier, {})
            total_games = ts.get("games", n_games)
            total_wins = ts.get("wins", win_count)
            win_pct = ts.get("win_pct", round(win_count / n_games * 100, 1) if n_games else 0.0)
            lines.append(f"| {display} | {total_wins} | {total_games} | {win_pct} |")

        lines.append("")

        # Show promotions/relegations that resulted from this tier
        for class_name in wins:
            p = players.get(class_name, {})
            current_tier = p.get("tier", tier)
            display = p.get("display_name", class_name)
            if current_tier != tier:
                direction = (
                    "Promoted" if _tier_rank(current_tier) > _tier_rank(tier) else "Relegated"
                )
                lines.append(f"{direction}: {display} → {current_tier}")

        lines.append("")

    # Skipped tiers footer
    if skipped:
        skipped_str = ", ".join(f"{t} (< 2 players)" for t in skipped)
        lines.append(f"## Skipped tiers: {skipped_str}")
        lines.append("")

    with open(summary_file, "w") as f:
        f.write("\n".join(lines))


def _tier_rank(tier: str) -> int:
    """Higher number = higher tier."""
    return {"inactive": 0, "L1": 1, "CH": 2, "PRM": 3}.get(tier, -1)


_README_START = "<!-- prettier-ignore-start -->"
_README_END = "<!-- prettier-ignore-end -->"

_TIER_LABEL = {"PRM": "Premier", "CH": "Championship", "L1": "Level 1", "inactive": "Inactive"}


def _standings_table(tier_players: list[tuple[str, dict]], tier: str) -> list[str]:
    lines = [
        "| Player | Win% | Wins | Games |",
        "|--------|------|------|-------|",
    ]
    for name, p in tier_players:
        display = p.get("display_name", name)
        ts = p.get("tier_stats", {}).get(tier, {})
        lines.append(
            f"| {display} | {ts.get('win_pct', 0.0)} | {ts.get('wins', 0)} | {ts.get('games', 0)} |"
        )
    return lines


def _update_readme(readme_path: str, lb_path: str) -> None:
    """Replace the <!-- leaderboard-start/end --> section in README.md with current standings."""
    if not os.path.exists(readme_path):
        return

    data = _load_lb(lb_path)
    players = data.get("players", {})

    def _sorted_players(tier: str) -> list[tuple[str, dict]]:
        pts = [(n, p) for n, p in players.items() if p.get("tier") == tier]
        pts.sort(key=lambda x: -x[1].get("tier_stats", {}).get(tier, {}).get("win_pct", 0.0))
        return pts

    lines: list[str] = [_README_START, "<!-- leaderboard-start -->"]

    for tier in ("PRM", "CH", "L1"):
        label = _TIER_LABEL[tier]
        tier_players = _sorted_players(tier)
        lines.append(f"### {label}")
        if tier_players:
            lines.extend(_standings_table(tier_players, tier))
        else:
            lines.append(f"*No players currently in {label}.*")
        lines.append("")

    inactive_players = _sorted_players("inactive")
    if inactive_players:
        lines.append("<details>")
        lines.append(f"<summary>Inactive ({len(inactive_players)} players)</summary>")
        lines.append("")
        lines.extend(_standings_table(inactive_players, "inactive"))
        lines.append("")
        lines.append("</details>")
        lines.append("")

    lines.extend(["<!-- leaderboard-end -->", _README_END])
    block = "\n".join(lines)

    with open(readme_path) as f:
        content = f.read()

    start_idx = content.find(_README_START)
    end_idx = content.find(_README_END)
    if start_idx == -1 or end_idx == -1:
        return

    updated = content[:start_idx] + block + content[end_idx + len(_README_END) :]
    with open(readme_path, "w") as f:
        f.write(updated)


def main() -> None:
    n_games = int(os.environ.get("N_GAMES", "250"))
    top_n = int(os.environ.get("TOP_N", "4"))
    lb_path = os.environ.get("LEADERBOARD_PATH", "leaderboard.yaml")
    summary_file = os.environ.get("SUMMARY_FILE", "season_summary.md")
    readme_path = os.environ.get("README_PATH", str(_REPO_ROOT / "README.md"))

    print(f"[run_season] n_games={n_games} top_n={top_n} lb={lb_path} summary={summary_file}")
    run_season(n_games, top_n, lb_path, summary_file, readme_path)


if __name__ == "__main__":
    main()
