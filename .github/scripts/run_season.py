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
import json
import math
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

from game.season.utils import _load_lb, form_pools  # noqa: E402

_DRY_RUN = os.environ.get("DRY_RUN", "").lower() in ("1", "true", "yes")
_POOL_MAX = 9  # maximum players per L1 pool; split when L1 exceeds this


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


def _run_players(players: list[str], n_games: int, lb_path: str) -> dict[str, int]:
    """Run n_games for a specific player list. Returns {name: win_count}."""
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
            str(len(players)),
            "--no-game-results",
            "--players",
            *players,
            "--results-file",
            results_file,
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=str(_REPO_ROOT))
        print(proc.stdout, end="")
        if proc.returncode != 0:
            print(f"[warn] game engine exited {proc.returncode}", file=sys.stderr)
            print(proc.stderr, end="", file=sys.stderr)
            return {}
        with open(results_file) as f:
            return json.load(f)
    finally:
        try:
            os.unlink(results_file)
        except FileNotFoundError:
            pass


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
            try:
                os.chmod(lb_path, 0o444)
                for i, pool in enumerate(pools):
                    print(f"  [pool {i + 1}/{n_pools}]: {pool}")
                    pool_wins = _run_players(pool, n_games, lb_path)
                    wins.update(pool_wins)
            finally:
                os.chmod(lb_path, 0o644)
        else:
            print(f"[run] {tier}: {len(players_in_tier)} players, {n_games} games each …")
            try:
                os.chmod(lb_path, 0o444)
                wins = _run_tier(tier, n_games, top_n, lb_path)
            finally:
                os.chmod(lb_path, 0o644)

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
    _update_readme(readme_path, lb_path, tier_results, n_games)
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


_README_START = "<!-- prettier-ignore-start -->"
_README_END = "<!-- prettier-ignore-end -->"

_TIER_LABEL = {"PRM": "Premier", "CH": "Championship", "L1": "Level 1", "inactive": "Inactive"}


def _standings_table(
    tier_players: list[tuple[str, dict]],
    tier: str,
    display_names: dict[str, str],
    tier_results: dict[str, dict[str, int]] | None = None,
    n_games: int = 0,
) -> list[str]:
    _RANK = {"inactive": 0, "L1": 1, "CH": 2, "PRM": 3}
    tier_rank = _RANK.get(tier, -1)

    def _is_relegated(name: str) -> bool:
        if not tier_results:
            return False
        return any(
            _RANK.get(t, -1) > tier_rank and name in results for t, results in tier_results.items()
        )

    def _sort_key(item: tuple[str, dict]) -> tuple:
        name, p = item
        if tier_results and n_games:
            if _is_relegated(name):
                return (0, 0.0)
            if name in tier_results.get(tier, {}):
                return (1, -(tier_results[tier][name] / n_games * 100))
            return (2, 0.0)
        return (1, -p.get("tier_stats", {}).get(tier, {}).get("win_pct", 0.0))

    def _season_pct(name: str, p: dict) -> str:
        if tier_results and n_games:
            if _is_relegated(name):
                return "Relegated"
            if name in tier_results.get(tier, {}):
                return str(round(tier_results[tier][name] / n_games * 100, 1))
            return "—"
        return str(p.get("tier_stats", {}).get(tier, {}).get("win_pct", 0.0))

    sorted_players = sorted(tier_players, key=_sort_key)

    lines = [
        f"| Player | Season W% | Wins in {tier} | Win % Total | Total Wins | Games |",
        "|--------|-----------|----------------|-------------|------------|-------|",
    ]
    for name, p in sorted_players:
        display = display_names.get(name, name)
        ts = p.get("tier_stats", {}).get(tier, {})
        all_stats = p.get("tier_stats", {}).values()
        total_wins = sum(t.get("wins", 0) for t in all_stats)
        total_games = sum(t.get("games", 0) for t in p.get("tier_stats", {}).values())
        total_win_pct = round(total_wins / total_games * 100, 1) if total_games else 0.0
        lines.append(
            f"| {display} | {_season_pct(name, p)} | {ts.get('wins', 0)} | {total_win_pct} | {total_wins} | {total_games} |"
        )
    return lines


def _quarter_leaderboard_table(
    players: dict[str, dict], display_names: dict[str, str]
) -> list[str]:
    """Unified quarter view — one row per player, win% columns for each tier.

    Sort order: QTD PRM W% desc → CH W% desc → L1 W% desc.
    """
    TIERS = ("PRM", "CH", "L1")

    def _sort_key(item: tuple[str, dict]) -> tuple:
        ts = item[1].get("tier_stats", {})
        return tuple(-ts.get(t, {}).get("win_pct", 0.0) for t in TIERS)

    sorted_players = sorted(players.items(), key=_sort_key)

    lines = [
        "| Player | Tier | PRM W% | CH W% | L1 W% | Total W% | Games |",
        "|--------|------|--------|-------|-------|----------|-------|",
    ]
    for name, p in sorted_players:
        display = display_names.get(name, name)
        tier_label = _TIER_LABEL.get(p.get("tier", ""), p.get("tier", ""))
        ts = p.get("tier_stats", {})

        prm_pct = str(ts["PRM"].get("win_pct", 0.0)) if "PRM" in ts else "—"
        ch_pct = str(ts["CH"].get("win_pct", 0.0)) if "CH" in ts else "—"
        l1_pct = str(ts["L1"].get("win_pct", 0.0)) if "L1" in ts else "—"

        total_wins = sum(t.get("wins", 0) for t in ts.values())
        total_games = sum(t.get("games", 0) for t in ts.values())
        total_pct = round(total_wins / total_games * 100, 1) if total_games else 0.0

        lines.append(
            f"| {display} | {tier_label} | {prm_pct} | {ch_pct} | {l1_pct} | {total_pct} | {total_games} |"
        )
    return lines


def _update_readme(
    readme_path: str,
    lb_path: str,
    tier_results: dict[str, dict[str, int]] | None = None,
    n_games: int = 0,
) -> None:
    """Replace the <!-- leaderboard-start/end --> section in README.md with current standings."""
    if _DRY_RUN:
        return
    if not os.path.exists(readme_path):
        return

    from game.components.leaderboard import build_display_names

    data = _load_lb(lb_path)
    players = data.get("players", {})
    display_names = build_display_names(players)

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
            lines.extend(_standings_table(tier_players, tier, display_names, tier_results, n_games))
        else:
            lines.append(f"*No players currently in {label}.*")
        lines.append("")

    inactive_players = _sorted_players("inactive")
    if inactive_players:
        lines.append("<details>")
        lines.append(f"<summary>Inactive ({len(inactive_players)} players)</summary>")
        lines.append("")
        lines.extend(
            _standings_table(inactive_players, "inactive", display_names, tier_results, n_games)
        )
        lines.append("")
        lines.append("</details>")
        lines.append("")

    lines.append("### Quarter Leaderboard")
    lines.append("")
    lines.extend(_quarter_leaderboard_table(players, display_names))
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
