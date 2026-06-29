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
    replaydb=None,
    week_num: int = 1,
    recording: bool = False,
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

            run_tournament(
                n_games=n_games,
                lb_path=lb_path,
                dashboard=dashboard,
                replaydb=replaydb,
                week_num=week_num,
                recording=recording,
            )
        else:
            from game.simulation.season import run_season

            run_season(
                n_games=n_games,
                top_n=int(os.environ.get("TOP_N", "4")),
                lb_path=lb_path,
                dashboard=dashboard,
                replaydb=replaydb,
                week_num=week_num,
                recording=recording,
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


def write_diff_report(
    original_standings: dict,
    replay_lb_path: str,
    output_file: Path,
) -> None:
    """Write a Markdown table comparing original vs replay per-player stats."""
    from game.season.utils import _load_lb

    replay_players = _load_lb(replay_lb_path).get("players", {})

    def _total_win_pct(player_data: dict) -> float:
        ts = player_data.get("tier_stats", {}).values()
        wins = sum(t.get("wins", 0) for t in ts)
        games = sum(t.get("games", 0) for t in ts)
        return round(wins / games * 100, 1) if games else 0.0

    all_names = sorted(set(original_standings) | set(replay_players))
    lines = [
        "# Replay Diff Report",
        "",
        "| Player | Orig Tier | Replay Tier | Orig Win% | Replay Win% | Delta |",
        "|--------|-----------|-------------|-----------|-------------|-------|",
    ]
    for name in all_names:
        orig = original_standings.get(name, {})
        repl = replay_players.get(name, {})
        display = orig.get("display_name") or repl.get("display_name") or name
        orig_tier = orig.get("tier", "—")
        repl_tier = repl.get("tier", "—")
        orig_pct = _total_win_pct(orig)
        repl_pct = _total_win_pct(repl)
        delta = round(repl_pct - orig_pct, 1)
        delta_str = f"+{delta}" if delta > 0 else str(delta)
        lines.append(
            f"| {display} | {orig_tier} | {repl_tier} | {orig_pct}% | {repl_pct}% | {delta_str}% |"
        )
    lines.append("")
    output_file.write_text("\n".join(lines))
    print(f"[done] Diff report written to {output_file}")


def write_tournament_diff_report(
    original_pool_results: dict,
    replay_pool_results: dict,
    original_standings: dict,
    replay_standings: dict,
    output_file: Path,
) -> None:
    """Write a Markdown table comparing original vs replay tournament pool results."""
    lines = [
        "# Tournament Replay Diff Report",
        "",
        "| Pool | Player | Orig Wins | Replay Wins | Δ Wins | Orig Tier | Replay Tier |",
        "|------|--------|-----------|-------------|--------|-----------|-------------|",
    ]
    for pool_key in sorted(set(original_pool_results) | set(replay_pool_results)):
        orig_pool = original_pool_results.get(pool_key, {})
        repl_pool = replay_pool_results.get(pool_key, {})
        pool_num = pool_key.replace("pool_", "")
        for name in sorted(set(orig_pool) | set(repl_pool)):
            orig = original_standings.get(name, {})
            repl = replay_standings.get(name, {})
            display = orig.get("display_name") or repl.get("display_name") or name
            orig_wins = orig_pool.get(name, 0)
            repl_wins = repl_pool.get(name, 0)
            delta = repl_wins - orig_wins
            delta_str = f"+{delta}" if delta > 0 else str(delta)
            lines.append(
                f"| {pool_num} | {display} | {orig_wins} | {repl_wins} | {delta_str}"
                f" | {orig.get('tier', '—')} | {repl.get('tier', '—')} |"
            )
    lines.append("")
    output_file.write_text("\n".join(lines))
    print(f"[done] Tournament diff report written to {output_file}")


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
    parser.add_argument(
        "--save-replay",
        action="store_true",
        default=False,
        help="Save seeds and initial state to a .replay file alongside the report.",
    )
    parser.add_argument(
        "--replay",
        type=Path,
        default=None,
        help="Path to a .replay file. Re-runs using stored seeds and leaderboard snapshot.",
    )
    parser.add_argument(
        "--save-leaderboard",
        action="store_true",
        default=False,
        help="When --replay is active, write the resulting leaderboard to leaderboard.yaml.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    import sys

    if args.save_replay and args.replay:
        print("[error] --save-replay and --replay are mutually exclusive", file=sys.stderr)
        sys.exit(1)
    if args.save_leaderboard and not args.replay:
        print("[error] --save-leaderboard requires --replay", file=sys.stderr)
        sys.exit(1)

    from game.season.utils import is_tournament_monday

    if not args.replay and not is_tournament_monday(args.start):
        print(
            f"[error] {args.start} is not a tournament Monday "
            "(must be the first Monday of Jan/Apr/Jul/Oct).",
            file=sys.stderr,
        )
        sys.exit(1)

    from game.simulation.replaydb import ReplayDB

    replaydb = None
    recording = False
    temp_lb_path: str | None = None

    quarter = current_quarter(args.start)
    output_file = args.output or Path(f"sim-{quarter}.md")
    replay_path = output_file.with_suffix(".replay")
    lb_path = os.environ.get("LEADERBOARD_PATH", "leaderboard.yaml")

    if args.save_replay:
        from game.season.utils import _load_lb

        replaydb = ReplayDB.create(replay_path)
        recording = True
        replaydb.save_meta(
            mode="quarter",
            step_date=args.start,
            quarter=quarter,
            n_games=args.n_games,
            top_n=int(os.environ.get("TOP_N", "4")),
            lb_snapshot=_load_lb(lb_path),
        )
        n_games = args.n_games
        mondays = compute_mondays(args.start)
    elif args.replay:
        import json
        import tempfile

        import yaml as _yaml

        replaydb = ReplayDB.load(args.replay)
        meta = replaydb.get_meta()
        lb_data = json.loads(meta["lb_snapshot"])
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
        _yaml.safe_dump(lb_data, tmp)
        tmp.close()
        temp_lb_path = tmp.name
        lb_path = temp_lb_path
        quarter = meta["quarter"]
        n_games = int(meta["n_games"])
        os.environ["TOP_N"] = meta["top_n"]
        step_date = date.fromisoformat(meta["step_date"])
        mondays = compute_mondays(step_date)
        output_file = args.output or Path(f"sim-{quarter}.md")
        print(f"[replay] {args.replay} — quarter {quarter}, {n_games} games/run")
    else:
        n_games = args.n_games
        mondays = compute_mondays(args.start)

    print(f"[simulate] {quarter}: {len(mondays)} Mondays, {n_games} games/run")
    print(f"[simulate] leaderboard: {lb_path}")
    print(f"[simulate] report: {output_file}")
    if not args.replay:
        print(
            f"[simulate] WARNING: {lb_path} will be modified in place. "
            f"Use `git checkout -- {lb_path}` or `just clean` to restore."
        )
    print()

    steps: list[dict] = []
    t_total = time.perf_counter()
    t_sim_end: list[float] = []

    try:
        if args.tui:
            from game.components.utils import apply_display_names, import_player_classes_from_dir
            from game.season.utils import _load_lb
            from game.tui import TuiAdapter

            _all = import_player_classes_from_dir(
                str(Path(__file__).parent.parent.parent / "players")
            )
            apply_display_names(_all, _load_lb(lb_path).get("players", {}))
            display_names = {type(p).__name__: p.name for p in _all}

            adapter: TuiAdapter | None = TuiAdapter(n_games=n_games, display_names=display_names)

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
                    output = run_step(
                        step_date,
                        mode,
                        n_games,
                        lb_path,
                        dashboard=adapter,
                        replaydb=replaydb,
                        week_num=i + 1,
                        recording=recording,
                    )
                    elapsed = time.perf_counter() - t0
                    print(f"[simulate] done in {elapsed:.1f}s")
                    steps.append({"date": step_date, "mode": mode, "output": output})
                    print()
                t_sim_end.append(time.perf_counter())

            adapter.run(_run_quarter)
        else:
            for i, (step_date, mode) in enumerate(mondays):
                label = f"Week {i + 1}"
                print(f"{'=' * 60}")
                print(f"[simulate] {step_date} — {label} (step {i + 1}/{len(mondays)})")
                print(f"{'=' * 60}")
                os.environ["TODAY"] = step_date.isoformat()
                t0 = time.perf_counter()
                output = run_step(
                    step_date,
                    mode,
                    n_games,
                    lb_path,
                    replaydb=replaydb,
                    week_num=i + 1,
                    recording=recording,
                )
                elapsed = time.perf_counter() - t0
                print(f"[simulate] done in {elapsed:.1f}s")
                steps.append({"date": step_date, "mode": mode, "output": output})
                print()

        write_report(steps, lb_path, output_file, n_games)

        if args.save_replay and replaydb:
            from game.season.utils import _load_lb

            replaydb.save_standings(_load_lb(lb_path).get("players", {}))
            print(f"[done] Replay saved to {replay_path}")

        if args.replay and replaydb:
            meta = replaydb.get_meta()
            if "original_standings" in meta:
                import json

                original_standings = json.loads(meta["original_standings"])
                diff_file = output_file.parent / (output_file.stem + "-diff.md")
                write_diff_report(original_standings, lb_path, diff_file)
            if args.save_leaderboard:
                import shutil

                real_lb = os.environ.get("LEADERBOARD_PATH", "leaderboard.yaml")
                shutil.copy(lb_path, real_lb)
                print("[done] Leaderboard updated from replay.")

    finally:
        if replaydb:
            replaydb.close()
        if temp_lb_path and Path(temp_lb_path).exists():
            Path(temp_lb_path).unlink()

    print(
        f"[simulate] total elapsed: {(t_sim_end[0] if t_sim_end else time.perf_counter()) - t_total:.1f}s"
    )


if __name__ == "__main__":
    main()
