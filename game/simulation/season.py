"""In-process season simulation for local bot tuning.

Replaces the subprocess-based approach of run_season.py for simulation use cases.
Does not post to GitHub or update README — DRY_RUN-safe by design.
"""

from __future__ import annotations

import argparse
import math
import os
import sys
from datetime import date
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent.parent
_POOL_MAX = 9


def _merge_h2h_stats(stats_list):
    """Merge die-exchange dicts from multiple pool GameStats into a single duck-typed object.

    Cross-pool pairs naturally have 0 in each other's dicts (they never played),
    so the merge is lossless within each pool and correctly returns 0 for cross-pool H2H.
    """
    from collections import namedtuple

    bluff: dict[str, dict[str, int]] = {}
    challenge: dict[str, dict[str, int]] = {}
    for s in stats_list:
        for player, d in s.die_losses_from_bluff.items():
            t = bluff.setdefault(player, {})
            for opp, v in d.items():
                t[opp] = t.get(opp, 0) + v
        for player, d in s.die_losses_from_challenge.items():
            t = challenge.setdefault(player, {})
            for opp, v in d.items():
                t[opp] = t.get(opp, 0) + v
    _H2HStats = namedtuple("_H2HStats", ["die_losses_from_bluff", "die_losses_from_challenge"])
    return _H2HStats(bluff, challenge)


def run_season(
    n_games: int,
    top_n: int,
    lb_path: str,
    players_dir: str | None = None,
    dashboard=None,
    replaydb=None,
    week_num: int = 1,
    recording: bool = False,
    profile_memory: bool = False,
) -> dict[str, dict[str, int]]:
    """Run one season step in-process. Returns {tier: {player: win_count}}.

    Args:
        n_games: Games per tier/pool.
        top_n: League capacity per PRM/CH tier (TOP_N).
        lb_path: Path to leaderboard.yaml.
        players_dir: Path to players/ directory. Defaults to repo root / players.
        dashboard: Optional TuiAdapter instance for live display.
        replaydb: Optional ReplayDB instance for seed recording/replay.
        week_num: Week number for seed indexing (default 1).
        recording: If True and replaydb is set, record seeds; if False, replay seeds.
        profile_memory: If True, also track tracemalloc peak-allocation bytes per
            algo() call (adds overhead — off by default).
    """
    from game.components.leaderboard import (
        apply_season_results,
        get_tier_players,
        settle_relegations,
    )
    from game.components.perf import PerfTracker
    from game.components.series import format_perf, format_results, run_series
    from game.components.utils import apply_display_names, import_player_classes_from_dir
    from game.season.utils import _load_lb, form_pools

    perf = PerfTracker(profile_memory=profile_memory)

    if players_dir is None:
        players_dir = str(_REPO_ROOT / "players")

    tier_order = ["inactive", "L1", "CH", "PRM"]
    tier_results: dict[str, dict[str, int]] = {}
    tier_series_stats: dict = {}

    for tier in tier_order:
        data = _load_lb(lb_path)
        tier_player_names = set(get_tier_players(data, tier))

        all_players = import_player_classes_from_dir(players_dir)
        apply_display_names(all_players, data.get("players", {}))
        players = [p for p in all_players if type(p).__name__ in tier_player_names]

        if len(players) < 2:
            print(f"[skip] {tier}: {len(players)} player(s) — need ≥ 2 to run games.")
            continue

        # class name → display name for pretty-printing (p.name after apply_display_names)
        display_map = {type(p).__name__: p.name for p in players}

        if tier == "L1" and len(players) > _POOL_MAX:
            n_pools = math.ceil(len(players) / _POOL_MAX)
            players_by_name = {type(p).__name__: p for p in players}
            seeded_names = sorted(
                tier_player_names,
                key=lambda n: (
                    -data["players"]
                    .get(n, {})
                    .get("tier_stats", {})
                    .get("L1", {})
                    .get("win_pct", 0.0)
                ),
            )
            pools_names = form_pools(seeded_names, n_pools)
            wins: dict[str, int] = {}
            pool_stats_list = []
            for i, pool_names in enumerate(pools_names):
                pool = [players_by_name[n] for n in pool_names if n in players_by_name]
                print(f"[run] L1 pool {i + 1}/{n_pools}: {pool_names}")
                if dashboard:
                    dashboard.start_series(f"L1 Pool {i + 1}")
                record_seeds: list[int] | None = (
                    [] if (replaydb is not None and recording) else None
                )
                replay_seeds: list[int] | None = (
                    replaydb.get_seeds(week_num, tier, i)
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
                    replaydb.save_seeds(week_num, tier, i, record_seeds)
                if dashboard:
                    dashboard.on_series_complete(f"L1 Pool {i + 1}", result)
                wins.update(result.wins)
                pool_stats_list.append(result.stats)
            tier_series_stats[tier] = _merge_h2h_stats(pool_stats_list)
            print(format_results({display_map.get(k, k): v for k, v in wins.items()}, n_games))
        else:
            print(f"[run] {tier}: {len(players)} players, {n_games} games …")
            if dashboard:
                dashboard.start_series(f"{tier} Tier")
            record_seeds: list[int] | None = [] if (replaydb is not None and recording) else None
            replay_seeds: list[int] | None = (
                replaydb.get_seeds(week_num, tier, 0)
                if (replaydb is not None and not recording)
                else None
            )
            result = run_series(
                players,
                n_games,
                tier=tier,
                on_game_complete=dashboard.update if dashboard else None,
                record_seeds=record_seeds,
                replay_seeds=replay_seeds,
                perf=perf,
            )
            if record_seeds is not None and replaydb is not None:
                replaydb.save_seeds(week_num, tier, 0, record_seeds)
            if dashboard:
                dashboard.on_series_complete(f"{tier} Tier", result)
            wins = result.wins
            tier_series_stats[tier] = result.stats
            print(format_results({display_map.get(k, k): v for k, v in wins.items()}, n_games))

        movements = apply_season_results(
            wins, n_games, tier, top_n, path=lb_path, stats=tier_series_stats.get(tier)
        )
        for m in movements:
            print(f"  {m}")
        print(f"[done] {tier}: leaderboard updated.")
        tier_results[tier] = wins

    relegations = settle_relegations(
        tier_results, top_n, path=lb_path, tier_stats=tier_series_stats
    )
    if relegations:
        print("[settle] cross-tier relegations:")
        for m in relegations:
            print(f"  {m}")

    perf_output = format_perf(perf, n_games)
    if perf_output:
        print(perf_output)

    return tier_results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run one season step in-process (simulation mode, no GitHub API)."
    )
    parser.add_argument(
        "date",
        nargs="?",
        default=None,
        help="Date override (YYYY-MM-DD). Sets TODAY env var. Default: system date.",
    )
    parser.add_argument(
        "--n-games",
        type=int,
        default=int(os.environ.get("N_GAMES", "1000")),
        help="Games per tier/pool. Default: N_GAMES env var or 1000.",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=int(os.environ.get("TOP_N", "4")),
        help="League capacity per PRM/CH tier. Default: TOP_N env var or 4.",
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
    top_n = args.top_n
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
            mode="season",
            step_date=step_date,
            quarter="",
            n_games=args.n_games,
            top_n=top_n,
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
        top_n = int(meta["top_n"])
        args.n_games = int(meta["n_games"])
        print(f"[replay] {args.replay} — season, {args.n_games} games/run")

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
                lambda: run_season(
                    args.n_games,
                    top_n,
                    lb_path,
                    dashboard=adapter,
                    replaydb=replaydb,
                    week_num=1,
                    recording=recording,
                    profile_memory=args.profile_memory,
                )
            )
        else:
            run_season(
                args.n_games,
                top_n,
                lb_path,
                replaydb=replaydb,
                week_num=1,
                recording=recording,
                profile_memory=args.profile_memory,
            )

        if args.save_replay and replaydb:
            from game.season.utils import _load_lb

            replaydb.save_standings(_load_lb(lb_path).get("players", {}))
            print(f"[done] Replay saved to sim-{step_date}.replay")

        if args.replay and replaydb:
            import json

            from game.simulation.quarter import write_diff_report

            meta = replaydb.get_meta()
            if "original_standings" in meta:
                original_standings = json.loads(meta["original_standings"])
                diff_file = Path(f"sim-{step_date}-diff.md")
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


if __name__ == "__main__":
    main()
