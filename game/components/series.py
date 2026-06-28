import logging
import secrets
from collections.abc import Callable
from dataclasses import dataclass

from game.components.stats import GameStats

logger = logging.getLogger(__name__)


@dataclass
class SeriesResult:
    wins: dict[str, int]
    stats: GameStats
    outcomes: list[dict] | None = None
    tier: str | None = None


def run_series(
    players: list,
    n_games: int,
    tier: str | None = None,
    capture_outcomes: bool = False,
    on_game_complete: Callable[[int, dict[str, int], GameStats], None] | None = None,
    record_seeds: list[int] | None = None,
    replay_seeds: list[int] | None = None,
) -> SeriesResult:
    """Runs n_games games between the given players and returns a SeriesResult.

    Args:
        players: List of player objects, each implementing the algo interface.
        n_games: Number of games to play.
        tier: League tier for this series ("L1", "CH", "PRM"), or None for
              tournament pools and untiered runs.
        capture_outcomes: If True, all round outcomes are included in the
              returned SeriesResult.outcomes. Defaults to False (outcomes not
              returned to caller, saving ~14 MB per 1000-game series).
        on_game_complete: Optional callback fired after each game with
              (game_num, wins, stats). Runs synchronously — no threading,
              no torn reads.

    Returns:
        SeriesResult with wins, stats, and optionally outcomes.
    """
    from game.components.script import game_orchestrator

    if record_seeds is not None and replay_seeds is not None:
        raise ValueError("record_seeds and replay_seeds are mutually exclusive")
    if replay_seeds is not None and len(replay_seeds) != n_games:
        raise ValueError(f"replay_seeds length {len(replay_seeds)} != n_games {n_games}")

    wins = {type(p).__name__: 0 for p in players}
    bet_history: list[dict] = []
    outcomes: list[dict] = []
    stats = GameStats()

    for game_num in range(1, n_games + 1):
        # Reset file logs so gamelog.log reflects only the current game
        for handler in logging.root.handlers:
            if isinstance(handler, logging.FileHandler):
                handler.stream.seek(0)
                handler.stream.truncate(0)

        if replay_seeds is not None:
            _seed: int | None = replay_seeds[game_num - 1]
        elif record_seeds is not None:
            _seed = secrets.randbits(64)
            record_seeds.append(_seed)
        else:
            _seed = None

        winner = game_orchestrator(
            players,
            game_id=game_num,
            bet_history=bet_history,
            outcomes=outcomes,
            stats=stats,
            tier=tier,
            seed=_seed,
        )
        wins[type(winner).__name__] += 1
        logger.info(f"Game {game_num}/{n_games}: {winner.name} wins")

        if on_game_complete is not None:
            on_game_complete(game_num, wins, stats)

    return SeriesResult(
        wins=wins,
        stats=stats,
        outcomes=outcomes if capture_outcomes else None,
        tier=tier,
    )


def format_results(wins: dict[str, int], n_games: int) -> str:
    """Formats series results as a summary table with win-rate bars.

    Args:
        wins: Dict mapping player name -> win count.
        n_games: Total games played (used to compute percentages).

    Returns:
        Formatted string ready to print.
    """
    BAR_WIDTH = 40

    name_w = max(len(n) for n in wins) + 2
    sorted_wins = sorted(wins.items(), key=lambda x: x[1], reverse=True)
    top = sorted_wins[0][1] if sorted_wins else 1

    header = f"  {'Player':<{name_w}}  {'Wins':>5}   {'Win %':>6}   Chart"
    divider = "  " + "-" * (name_w + 5 + 9 + BAR_WIDTH + 5)

    rows = []
    for name, count in sorted_wins:
        pct = count / n_games * 100
        bar_len = round(count / top * BAR_WIDTH) if top else 0
        bar = "█" * bar_len
        rows.append(f"  {name:<{name_w}}  {count:>5}   {pct:>5.1f}%   {bar}")

    lines = [
        f"\n=== Series Results — {n_games} games ===\n",
        header,
        divider,
        *rows,
    ]
    return "\n".join(lines)
