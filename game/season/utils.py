"""Shared utilities for season scripts."""

import json
import os
import subprocess
import sys
import tempfile
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


def run_game_with_retry(
    base_cmd: list[str],
    env: dict,
    cwd: Path,
    warn_label: str = "",
) -> tuple[dict[str, int], list[str]]:
    """Run a `python -m game ...` subprocess, retrying once with
    `--exclude <offender>` if a security violation is detected, so the
    offender's innocent tier/pool-mates still get real games this run
    instead of the whole batch being discarded.

    *base_cmd* must be the full command WITHOUT `--results-file` or
    `--exclude` — both are added here.

    Returns (wins, offenders): wins is {} if the run is unrecoverable
    (either an ordinary non-127 failure, or a second violation on the retry);
    offenders is every security-violation offender detected (0, 1, or 2
    entries — detection halts the game engine immediately on the first
    violation per invocation, so at most one new offender can appear per
    attempt). This function never touches the leaderboard — the caller is
    responsible for actually expelling each offender via expel_player(),
    once it's safe to do so (e.g. reset_season.py's run_pools() must wait
    until lb_path is writable again).
    """
    offenders: list[str] = []
    for _attempt in range(2):  # original attempt + one retry excluding the offender
        with tempfile.NamedTemporaryFile(
            suffix=".json", prefix="game_results_", delete=False
        ) as tmp:
            results_file = tmp.name
        try:
            cmd = [*base_cmd, "--results-file", results_file]
            if offenders:
                cmd += ["--exclude", *offenders]
            proc = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=str(cwd))
            print(proc.stdout, end="")
            if proc.returncode != 0:
                offender = None
                if proc.returncode == 127:
                    for line in proc.stderr.splitlines():
                        if "SECURITY_VIOLATION:" in line:
                            offender = line.split(":", 1)[1]
                            break
                if offender:
                    print(f"[CRITICAL] Security violation by {offender}!", file=sys.stderr)
                    offenders.append(offender)
                    continue
                print(f"[warn] game engine exited {proc.returncode}{warn_label}", file=sys.stderr)
                print(proc.stderr, end="", file=sys.stderr)
                return {}, offenders
            with open(results_file) as f:
                return json.load(f), offenders
        finally:
            try:
                os.unlink(results_file)
            except FileNotFoundError:
                pass
    return {}, offenders


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
    from game.components.leaderboard import avatar_img_tag

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
        display = f"{avatar_img_tag(name, p)} {display_names.get(name, name)}"
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
    from game.components.leaderboard import avatar_img_tag

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
        display = f"{avatar_img_tag(name, p)} {display_names.get(name, name)}"
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
    dry_run: bool = False,
) -> None:
    """Replace the <!-- leaderboard-start/end --> section in README.md with current standings.

    Shared by run_season.py (regular Monday tiers, which passes tier_results
    to show this week's per-tier movement) and reset_season.py (quarterly
    tournament, which has no tier_results — pure re-render from leaderboard.yaml).
    """
    if dry_run:
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
