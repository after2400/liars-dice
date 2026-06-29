"""In-process season simulation for local bot tuning.

Replaces the subprocess-based approach of run_season.py for simulation use cases.
Does not post to GitHub or update README — DRY_RUN-safe by design.
"""

from __future__ import annotations

import argparse
import math
import os
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
) -> dict[str, dict[str, int]]:
    """Run one season step in-process. Returns {tier: {player: win_count}}.

    Args:
        n_games: Games per tier/pool.
        top_n: League capacity per PRM/CH tier (TOP_N).
        lb_path: Path to leaderboard.yaml.
        players_dir: Path to players/ directory. Defaults to repo root / players.
        dashboard: Optional TuiAdapter instance for live display.
    """
    from game.components.leaderboard import (
        apply_season_results,
        get_tier_players,
        settle_relegations,
    )
    from game.components.series import format_results, run_series
    from game.components.utils import apply_display_names, import_player_classes_from_dir
    from game.season.utils import _load_lb, form_pools

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
                result = run_series(
                    pool,
                    n_games,
                    on_game_complete=dashboard.update if dashboard else None,
                )
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
            result = run_series(
                players,
                n_games,
                tier=tier,
                on_game_complete=dashboard.update if dashboard else None,
            )
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
    args = parser.parse_args()

    if args.date:
        os.environ["TODAY"] = args.date

    lb_path = os.environ.get("LEADERBOARD_PATH", "leaderboard.yaml")
    top_n = args.top_n

    if args.tui:
        from game.components.utils import apply_display_names, import_player_classes_from_dir
        from game.season.utils import _load_lb
        from game.tui import TuiAdapter

        _all = import_player_classes_from_dir(str(_REPO_ROOT / "players"))
        apply_display_names(_all, _load_lb(lb_path).get("players", {}))
        display_names = {type(p).__name__: p.name for p in _all}

        adapter = TuiAdapter(n_games=args.n_games, display_names=display_names)
        adapter.run(lambda: run_season(args.n_games, top_n, lb_path, dashboard=adapter))
    else:
        run_season(args.n_games, top_n, lb_path)


if __name__ == "__main__":
    main()
