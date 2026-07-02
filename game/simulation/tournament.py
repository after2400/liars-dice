"""In-process tournament simulation for local bot tuning.

Replaces the subprocess-based approach of reset_season.py for simulation use cases.
Does not create GitHub issues — DRY_RUN-safe by design.
"""

from __future__ import annotations

import argparse
import math
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent.parent


def run_tournament(
    n_games: int,
    lb_path: str,
    players_dir: str | None = None,
    dashboard=None,
    replaydb=None,
    week_num: int = 1,
    recording: bool = False,
    profile_memory: bool = False,
) -> dict[str, dict[str, int]]:
    """Run a full tournament in-process. Returns {pool_key: {player: win_count}}.

    Zeroes tier_stats, seeds players by prior tier+win%, forms pools,
    runs each pool's games, then assigns placements top-down.

    Args:
        n_games: Games per pool.
        lb_path: Path to leaderboard.yaml.
        players_dir: Path to players/ directory. Defaults to repo root / players.
        dashboard: Optional TuiAdapter instance for live display.
        replaydb: Optional ReplayDB instance for seed recording/replay.
        week_num: Week number for seed indexing (default 1 for tournament).
        recording: If True and replaydb is set, record seeds; if False, replay seeds.
        profile_memory: If True, also track tracemalloc peak-allocation bytes per
            algo() call (adds overhead — off by default).
    """
    from game.components.leaderboard import get_tier_players
    from game.components.perf import PerfTracker
    from game.components.series import format_perf, format_results, run_series
    from game.components.utils import apply_display_names, import_player_classes_from_dir
    from game.season.utils import _load_lb, _save_lb, current_quarter, form_pools

    perf = PerfTracker(profile_memory=profile_memory)

    if players_dir is None:
        players_dir = str(_REPO_ROOT / "players")

    data = _load_lb(lb_path)
    quarter = current_quarter()

    # Compute seeding order BEFORE zeroing tier_stats
    tier_order_seed = ["PRM", "CH", "L1", "DED", "inactive"]
    players_data = data.get("players", {})

    def _win_pct(name: str) -> float:
        ts = players_data.get(name, {}).get("tier_stats", {})
        total_w = sum(t.get("wins", 0) for t in ts.values())
        total_g = sum(t.get("games", 0) for t in ts.values())
        return total_w / total_g if total_g else 0.0

    seeded: list[str] = []
    for tier in tier_order_seed:
        in_tier = get_tier_players(data, tier)
        in_tier.sort(key=_win_pct, reverse=True)
        seeded.extend(in_tier)

    # Zero tier_stats for the new quarter
    for player in data.get("players", {}).values():
        player["tier_stats"] = {}
    data.setdefault("tournament_state", {})
    data["tournament_state"]["quarter"] = quarter
    _save_lb(data, lb_path)
    print(f"[done] zero_stats: all tier_stats cleared for {quarter}")

    # Form pools
    n_players = len(seeded)
    n_pools = max(1, math.ceil(n_players / 8))
    pools = form_pools(seeded, n_pools)

    # Load player classes
    all_players = import_player_classes_from_dir(players_dir)
    apply_display_names(all_players, data.get("players", {}))
    players_by_name = {type(p).__name__: p for p in all_players}
    # class name → display name for pretty-printing
    display_map = {type(p).__name__: p.name for p in all_players}

    pool_results: dict[str, dict[str, int]] = {}

    for i, pool_names in enumerate(pools):
        key = f"pool_{i}"
        pool = [players_by_name[n] for n in pool_names if n in players_by_name]
        if len(pool) < 2:
            print(f"[skip] {key}: {len(pool)} player(s) — need ≥ 2.")
            continue
        print(f"[run] {key}: {pool_names}")
        if dashboard:
            dashboard.start_series(key.replace("_", " ").title())

        record_seeds: list[int] | None = [] if (replaydb is not None and recording) else None
        replay_seeds: list[int] | None = (
            replaydb.get_seeds(week_num, None, i)
            if (replaydb is not None and not recording)
            else None
        )

        result = run_series(
            pool,
            n_games,
            on_game_complete=dashboard.update if dashboard else None,
            record_seeds=record_seeds,
            replay_seeds=replay_seeds,
            perf=perf,
        )

        if record_seeds is not None and replaydb is not None:
            replaydb.save_seeds(week_num, None, i, record_seeds)

        if dashboard:
            dashboard.on_series_complete(key, result)
        pool_results[key] = result.wins
        display_wins = {display_map.get(k, k): v for k, v in result.wins.items()}
        print(format_results(display_wins, n_games))
        print(f"[done] {key}: {display_wins}")

    perf_output = format_perf(perf, n_games)
    if perf_output:
        print(perf_output)

    # Assign placements
    _assign_placements(lb_path, pool_results)
    return pool_results


def _assign_placements(lb_path: str, pool_results: dict[str, dict[str, int]]) -> None:
    """Assign tier placements from pool results, top-down by total win count."""
    from game.components.leaderboard import tier_capacities
    from game.season.utils import _load_lb, _save_lb

    data = _load_lb(lb_path)
    all_wins: dict[str, int] = {}
    for wins in pool_results.values():
        all_wins.update(wins)

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

    data["tournament_state"]["pool_results"] = pool_results
    _save_lb(data, lb_path)
    print(f"[done] assign_placements: {n_players} players placed")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run tournament in-process (simulation mode, no GitHub API)."
    )
    parser.add_argument(
        "--date",
        default=None,
        help="Date override (YYYY-MM-DD). Sets TODAY env var.",
    )
    parser.add_argument(
        "--n-games",
        type=int,
        default=int(os.environ.get("N_GAMES", "1000")),
        help="Games per pool. Default: N_GAMES env var or 1000.",
    )
    parser.add_argument(
        "--tui",
        action="store_true",
        default=False,
        help="Launch the Textual TUI dashboard.",
    )
    parser.add_argument(
        "--profile-memory",
        action="store_true",
        default=False,
        help="Enable tracemalloc-based peak memory profiling per algo() call (adds overhead).",
    )
    parser.add_argument("--save-replay", action="store_true", default=False)
    parser.add_argument("--replay", type=Path, default=None)
    parser.add_argument("--save-leaderboard", action="store_true", default=False)
    args = parser.parse_args()

    if args.save_replay and args.replay:
        print("[error] --save-replay and --replay are mutually exclusive", file=sys.stderr)
        sys.exit(1)
    if args.save_leaderboard and not args.replay:
        print("[error] --save-leaderboard requires --replay", file=sys.stderr)
        sys.exit(1)

    if args.date:
        os.environ["TODAY"] = args.date

    lb_path = os.environ.get("LEADERBOARD_PATH", "leaderboard.yaml")
    step_date = date.fromisoformat(args.date) if args.date else date.today()

    from game.simulation.replaydb import ReplayDB

    replaydb = None
    recording = False
    temp_lb_path: str | None = None

    if args.save_replay:
        from game.season.utils import _load_lb

        replay_path = Path(f"sim-{step_date}.replay")
        replaydb = ReplayDB.create(replay_path)
        recording = True
        replaydb.save_meta(
            mode="tournament",
            step_date=step_date,
            quarter="",
            n_games=args.n_games,
            top_n=int(os.environ.get("TOP_N", "4")),
            lb_snapshot=_load_lb(lb_path),
        )
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
        args.n_games = int(meta["n_games"])
        os.environ["TOP_N"] = meta["top_n"]
        print(f"[replay] {args.replay} — tournament, {args.n_games} games/run")

    try:
        if args.tui:
            from game.components.utils import apply_display_names, import_player_classes_from_dir
            from game.season.utils import _load_lb
            from game.tui import TuiAdapter

            _all = import_player_classes_from_dir(str(_REPO_ROOT / "players"))
            apply_display_names(_all, _load_lb(lb_path).get("players", {}))
            display_names = {type(p).__name__: p.name for p in _all}
            adapter = TuiAdapter(n_games=args.n_games, display_names=display_names)
            adapter.run(
                lambda: run_tournament(
                    args.n_games,
                    lb_path,
                    dashboard=adapter,
                    replaydb=replaydb,
                    week_num=1,
                    recording=recording,
                    profile_memory=args.profile_memory,
                )
            )
        else:
            run_tournament(
                args.n_games,
                lb_path,
                replaydb=replaydb,
                week_num=1,
                recording=recording,
                profile_memory=args.profile_memory,
            )

        if args.save_replay and replaydb:
            from game.season.utils import _load_lb

            lb_data = _load_lb(lb_path)
            replaydb.save_standings(lb_data.get("players", {}))
            replaydb.save_pool_results(lb_data.get("tournament_state", {}).get("pool_results", {}))
            print(f"[done] Replay saved to sim-{step_date}.replay")

        if args.replay and replaydb:
            import json

            from game.season.utils import _load_lb
            from game.simulation.quarter import write_tournament_diff_report

            meta = replaydb.get_meta()
            if "original_standings" in meta and "original_pool_results" in meta:
                lb_data = _load_lb(lb_path)
                diff_file = Path(f"sim-{step_date}-diff.md")
                write_tournament_diff_report(
                    json.loads(meta["original_pool_results"]),
                    lb_data.get("tournament_state", {}).get("pool_results", {}),
                    json.loads(meta["original_standings"]),
                    lb_data.get("players", {}),
                    diff_file,
                )
            elif "original_standings" in meta:
                print(
                    "[warn] Replay file predates pool_results saving — diff skipped.",
                    file=__import__("sys").stderr,
                )
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


if __name__ == "__main__":
    main()
