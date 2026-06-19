"""Quarter simulation — runs a full quarter locally with DRY_RUN=true."""

from __future__ import annotations

import argparse
import os
import subprocess
import time
from datetime import date, datetime, timedelta
from io import StringIO
from pathlib import Path

from game.season.utils import current_quarter, next_tournament_monday

_REPO_ROOT = Path(__file__).parent.parent.parent
_SCRIPTS = _REPO_ROOT / ".github" / "scripts"


def compute_mondays(start: date) -> list[tuple[date, str]]:
    """Return [(date, mode), ...] for every Monday in the quarter starting at start.

    start must be a tournament Monday. The sequence runs up to (not including)
    the next tournament Monday.
    """
    end = next_tournament_monday(start + timedelta(days=1))
    mondays: list[tuple[date, str]] = []
    d = start
    while d < end:
        mode = "tournament" if d == start else "season"
        mondays.append((d, mode))
        d += timedelta(days=7)
    return mondays


def run_step(
    step_date: date,
    mode: str,
    n_games: int,
    lb_path: str,
) -> str:
    """Run one Monday step via subprocess. Always sets DRY_RUN=true.

    Streams stdout+stderr to console line-by-line while accumulating for return.
    """
    script = _SCRIPTS / ("reset_season.py" if mode == "tournament" else "run_season.py")
    env = {
        **os.environ,
        "TODAY": step_date.isoformat(),
        "DRY_RUN": "true",
        "N_GAMES": str(n_games),
        "LEADERBOARD_PATH": lb_path,
    }
    proc = subprocess.Popen(
        ["uv", "run", "python", str(script)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
        cwd=str(_REPO_ROOT),
    )
    buf = StringIO()
    for line in proc.stdout:
        print(line, end="", flush=True)
        buf.write(line)
    proc.wait()
    return buf.getvalue()


_TIER_LABEL = {"PRM": "Premier", "CH": "Championship", "L1": "Level 1"}


def write_report(
    steps: list[dict],
    lb_path: str,
    output_file: Path,
    n_games: int,
) -> None:
    """Write a plain-Markdown simulation report."""
    from game.components.leaderboard import build_display_names
    from game.season.utils import _load_lb

    data = _load_lb(lb_path)
    players = data.get("players", {})
    display_names = build_display_names(players)

    # Derive quarter from the first step date, or fall back to today.
    first_date = steps[0]["date"] if steps else date.today()
    quarter = current_quarter(first_date)

    lines: list[str] = [
        f"# Quarter Simulation: {quarter}",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | **Start:** {first_date} | **Mondays:** {len(steps)} | **Games/run:** {n_games}",
        "",
    ]

    for i, step in enumerate(steps):
        d = step["date"]
        mode = step["mode"]
        output = step["output"]

        if mode == "tournament":
            label = "Tournament"
        else:
            label = f"Week {i}"

        lines.append(f"## {d} — {label}")
        lines.append("")
        lines.append(output.rstrip())
        lines.append("")

    lines += ["---", "", "## Final Standings", ""]

    for tier, label in _TIER_LABEL.items():
        tier_players = [(n, p) for n, p in players.items() if p.get("tier") == tier]
        tier_players.sort(
            key=lambda x: -x[1].get("tier_stats", {}).get(tier, {}).get("win_pct", 0.0)
        )
        lines.append(f"### {label}")
        if tier_players:
            lines.append(f"| Player | Win % in {tier} | Wins | Win % Total | Total Wins | Games |")
            lines.append("|--------|----------------|------|-------------|------------|-------|")
            for name, p in tier_players:
                display = display_names.get(name, name)
                ts = p.get("tier_stats", {}).get(tier, {})
                all_ts = p.get("tier_stats", {}).values()
                total_wins = sum(t.get("wins", 0) for t in all_ts)
                total_games = sum(t.get("games", 0) for t in p.get("tier_stats", {}).values())
                total_pct = round(total_wins / total_games * 100, 1) if total_games else 0.0
                lines.append(
                    f"| {display} | {ts.get('win_pct', 0.0)} | {ts.get('wins', 0)} "
                    f"| {total_pct} | {total_wins} | {total_games} |"
                )
        else:
            lines.append(f"*No players currently in {label}.*")
        lines.append("")

    inactive = [n for n, p in players.items() if p.get("tier") == "inactive"]
    if inactive:
        inactive_names = ", ".join(display_names.get(n, n) for n in inactive)
        lines.append(f"*Inactive: {inactive_names}*")
        lines.append("")

    output_file.write_text("\n".join(lines))
    print(f"[done] Report written to {output_file}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Simulate a full quarter locally (DRY_RUN=true, no GitHub changes)."
    )
    parser.add_argument(
        "--start",
        type=lambda s: date.fromisoformat(s),
        default=next_tournament_monday(),
        help="Tournament Monday to start from (YYYY-MM-DD). Default: next upcoming.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Report output path. Default: sim-YYYY-QN.md in current directory.",
    )
    parser.add_argument(
        "--n-games",
        type=int,
        default=int(os.environ.get("N_GAMES", "1000")),
        help="Games per tier/pool per run. Default: N_GAMES env var or 1000.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    import sys

    from game.season.utils import is_tournament_monday

    if not is_tournament_monday(args.start):
        print(
            f"[error] {args.start} is not a tournament Monday "
            "(must be the first Monday of Jan/Apr/Jul/Oct).",
            file=sys.stderr,
        )
        sys.exit(1)

    quarter = current_quarter(args.start)
    output_file = args.output or Path(f"sim-{quarter}.md")
    lb_path = os.environ.get("LEADERBOARD_PATH", "leaderboard.yaml")

    mondays = compute_mondays(args.start)
    print(f"[simulate] {quarter}: {len(mondays)} Mondays, {args.n_games} games/run")
    print(f"[simulate] leaderboard: {lb_path}")
    print(f"[simulate] report: {output_file}")
    print(
        f"[simulate] WARNING: {lb_path} will be modified in place. Use `git checkout -- {lb_path}` or `just clean` to restore."
    )
    print()

    steps: list[dict] = []
    t_total = time.perf_counter()
    for i, (step_date, mode) in enumerate(mondays):
        label = "Tournament" if mode == "tournament" else "season"
        print(f"{'=' * 60}")
        print(f"[simulate] {step_date} — {label} (week {i + 1}/{len(mondays)})")
        print(f"{'=' * 60}")
        t0 = time.perf_counter()
        output = run_step(step_date, mode, args.n_games, lb_path)
        elapsed = time.perf_counter() - t0
        print(f"[simulate] done in {elapsed:.1f}s")
        steps.append({"date": step_date, "mode": mode, "output": output})
        print()

    write_report(steps, lb_path, output_file, args.n_games)
    print(f"[simulate] total elapsed: {time.perf_counter() - t_total:.1f}s")


if __name__ == "__main__":
    main()
