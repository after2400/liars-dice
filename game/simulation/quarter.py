"""Quarter simulation — runs a full quarter locally with DRY_RUN=true."""

from __future__ import annotations

import argparse
import os
import time
from datetime import date, datetime, timedelta
from pathlib import Path

from game.season.utils import current_quarter, next_tournament_monday

_REPO_ROOT = Path(__file__).parent.parent.parent


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
    dashboard=None,
) -> str:
    """Run one Monday step in-process. Returns captured stdout text for the report.

    TuiAdapter writes to stderr so it reaches the terminal even while stdout
    is redirected here for report capture.
    """
    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        if mode == "tournament":
            from game.simulation.tournament import run_tournament

            run_tournament(n_games=n_games, lb_path=lb_path, dashboard=dashboard)
        else:
            from game.simulation.season import run_season

            run_season(
                n_games=n_games,
                top_n=int(os.environ.get("TOP_N", "4")),
                lb_path=lb_path,
                dashboard=dashboard,
            )
    output = buf.getvalue()
    print(output, end="")
    return output


_TIER_LABEL = {"PRM": "Premier", "CH": "Championship", "L1": "Level 1"}


def _format_output(output: str) -> str:
    """Wrap Series Results blocks in code fences; add trailing spaces to log lines."""
    lines = output.splitlines()
    result = []
    in_chart = False

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("=== Series Results"):
            in_chart = True
            result.append("```")
            result.append(line)
            continue

        if in_chart:
            if stripped.startswith(("[", "Promoted", "Relegated", "Playing")):
                result.append("```")
                in_chart = False
                result.append(line + "  " if stripped else line)
            else:
                result.append(line)
            continue

        result.append(line + "  " if stripped else line)

    if in_chart:
        result.append("```")

    return "\n".join(result)


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
        output = step["output"]

        label = f"Week {i + 1}"

        lines.append(f"## {d} — {label}")
        lines.append("")
        lines.append(_format_output(output.rstrip()))
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
    parser.add_argument(
        "--tui",
        action="store_true",
        default=False,
        help="Launch the Textual TUI dashboard.",
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
        f"[simulate] WARNING: {lb_path} will be modified in place. "
        f"Use `git checkout -- {lb_path}` or `just clean` to restore."
    )
    print()

    steps: list[dict] = []
    t_total = time.perf_counter()

    if args.tui:
        from game.components.utils import apply_display_names, import_player_classes_from_dir
        from game.season.utils import _load_lb
        from game.tui import TuiAdapter

        _all = import_player_classes_from_dir(str(Path(__file__).parent.parent.parent / "players"))
        apply_display_names(_all, _load_lb(lb_path).get("players", {}))
        display_names = {type(p).__name__: p.name for p in _all}

        adapter: TuiAdapter | None = TuiAdapter(n_games=args.n_games, display_names=display_names)

        def _run_quarter() -> None:
            week = 1
            for i, (step_date, mode) in enumerate(mondays):
                if mode == "tournament":
                    step_label = "Week 1"
                else:
                    week += 1
                    step_label = f"Week {week}"
                adapter.start_step(step_label)
                print(f"{'=' * 60}")
                print(f"[simulate] {step_date} — {step_label} (step {i + 1}/{len(mondays)})")
                print(f"{'=' * 60}")
                os.environ["TODAY"] = step_date.isoformat()
                t0 = time.perf_counter()
                output = run_step(step_date, mode, args.n_games, lb_path, dashboard=adapter)
                elapsed = time.perf_counter() - t0
                print(f"[simulate] done in {elapsed:.1f}s")
                steps.append({"date": step_date, "mode": mode, "output": output})
                print()

        adapter.run(_run_quarter)
    else:
        for i, (step_date, mode) in enumerate(mondays):
            label = f"Week {i + 1}"
            print(f"{'=' * 60}")
            print(f"[simulate] {step_date} — {label} (step {i + 1}/{len(mondays)})")
            print(f"{'=' * 60}")
            os.environ["TODAY"] = step_date.isoformat()
            t0 = time.perf_counter()
            output = run_step(step_date, mode, args.n_games, lb_path, dashboard=None)
            elapsed = time.perf_counter() - t0
            print(f"[simulate] done in {elapsed:.1f}s")
            steps.append({"date": step_date, "mode": mode, "output": output})
            print()

    write_report(steps, lb_path, output_file, args.n_games)
    print(f"[simulate] total elapsed: {time.perf_counter() - t_total:.1f}s")


if __name__ == "__main__":
    main()
