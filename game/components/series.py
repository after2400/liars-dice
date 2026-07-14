import logging
import secrets
from collections.abc import Callable
from dataclasses import dataclass

from game.components.isolation.pool import WorkerPool
from game.components.isolation.readmodel import ReadModelWriter
from game.components.isolation.seeding import derive_worker_seed
from game.components.isolation.worker import WorkerConfig
from game.components.perf import PerfTracker
from game.components.stats import GameStats

logger = logging.getLogger(__name__)

# --- ReadModelWriter sizing --------------------------------------------------
# One ReadModelWriter is allocated per SERIES (not per game) and accumulates
# every game's bet_history/outcomes for the series' whole lifetime — same
# lifetime as run_series's own `bet_history`/`outcomes` lists below. Its
# shared-memory block has a fixed capacity (BufferError if exceeded), so it
# must be sized for the whole series up front.
#
# Sized by BOTH n_games and player count — not n_games alone. Both bet/outcome
# record counts per game AND each outcome's pickled size (its "hands" dict has
# one entry per still-active player) scale with roster size, and production
# callers span a wide range: season.py/tournament.py keep series small (TOP_N=4
# for PRM/CH, _POOL_MAX=9 for L1 pools), but game/__main__.py's standalone CLI
# pulls in the WHOLE unregistered roster as "challengers" (tens of players) —
# a flat per-game constant undersized that case even at n_games=5.
#
# Measured against the real players/ directory (game_orchestrator, 10 games
# each, varying roster size):
#   n_players=4:  ~44.8 bet-records/game, ~16.8 outcome-records/game, ~247B/outcome
#   n_players=12: ~185.3 bet-records/game, ~55.8 outcome-records/game, ~355B/outcome
#   n_players=27: ~628.6 bet-records/game, ~131.0 outcome-records/game, ~543B/outcome
# Both record counts and outcome size scale ~linearly with player count. The
# constants below fit that data with a ~1.5x safety margin baked in.
_BET_RECORD_BYTES = 148  # struct.calcsize of readmodel.py's fixed bet-record layout
# (_BET_FMT = "<II128sIII"); duplicated here (not imported) since that's a
# module-private implementation detail of ReadModelWriter — keep in sync if
# readmodel.py's _NAME_FIELD_SIZE/_BET_FMT ever changes.
_OUTCOME_INDEX_ENTRY_BYTES = 4

# ReadModelWriter._compute_layout splits size_bytes into FIXED fractions
# regardless of actual demand (game/components/isolation/readmodel.py):
_BET_REGION_FRACTION = 0.5
_OUTCOME_INDEX_FRACTION = 0.1
_OUTCOME_DATA_FRACTION = 0.2  # remainder after bet(0.5) + outcome-index(0.1) + stats(0.2)

_BET_RECORDS_PER_PLAYER_PER_GAME = 35  # measured ~23.3/player/game @ n=27, ~1.5x margin
_OUTCOME_RECORDS_PER_PLAYER_PER_GAME = 8  # measured ~4.85/player/game @ n=27, ~1.6x margin
_OUTCOME_BYTES_BASE = 300  # linear-fit intercept ~196B (measured), rounded up
_OUTCOME_BYTES_PER_PLAYER = 20  # linear-fit slope ~12.84B/player (measured), ~1.5x margin

# Header + stats double-buffer floor — independent of n_games/players (GameStats
# snapshots are bounded aggregates, not a growing per-game log).
_READMODEL_BASE_BYTES = 256 * 1024


def _readmodel_size_bytes(n_games: int, n_players: int) -> int:
    n_players = max(n_players, 1)

    bet_bytes_per_game = n_players * _BET_RECORDS_PER_PLAYER_PER_GAME * _BET_RECORD_BYTES
    outcome_index_bytes_per_game = (
        n_players * _OUTCOME_RECORDS_PER_PLAYER_PER_GAME * _OUTCOME_INDEX_ENTRY_BYTES
    )
    avg_outcome_bytes = _OUTCOME_BYTES_BASE + _OUTCOME_BYTES_PER_PLAYER * n_players
    outcome_data_bytes_per_game = (
        n_players * _OUTCOME_RECORDS_PER_PLAYER_PER_GAME * avg_outcome_bytes
    )

    # Each region gets a fixed fraction of size_bytes, so the binding constraint
    # is whichever region needs the largest total size_bytes to fit its demand.
    usable_bytes_per_game = max(
        bet_bytes_per_game / _BET_REGION_FRACTION,
        outcome_index_bytes_per_game / _OUTCOME_INDEX_FRACTION,
        outcome_data_bytes_per_game / _OUTCOME_DATA_FRACTION,
    )
    return _READMODEL_BASE_BYTES + int(n_games * usable_bytes_per_game)


def _require_isolation_specs(players: list) -> list:
    """Validates every player has a `_isolation_spec` BEFORE any isolation
    resource (ReadModelWriter's shared-memory block, WorkerPool's
    subprocesses) is allocated, so a bad player list fails loudly without
    leaking anything for the caller to clean up."""
    specs = []
    for p in players:
        spec = getattr(p, "_isolation_spec", None)
        if spec is None:
            raise ValueError(
                f"run_series(isolated=True) requires every player to be loaded via "
                "import_player_classes_from_dir()/import_player_specs_from_dir() "
                "(game/components/utils.py) so its source file + class name are "
                f"known for reloading inside an isolated worker; {type(p).__name__!r} "
                "has no `_isolation_spec` attribute (it was likely constructed "
                "directly). Pass isolated=False to run this series in-process instead."
            )
        specs.append(spec)
    return specs


def _build_worker_configs(
    players: list, specs: list, readmodel_name: str, replay_seeds: list[int] | None
) -> list[WorkerConfig]:
    """One WorkerConfig per player, built ONCE for the whole series.

    Owner-approved scope reduction (2026-07-14): per-game worker reseeding
    (`derive_worker_seed` called again before each game) is NOT implemented —
    it would require extending the parent<->worker pipe protocol with a new
    "reseed" message, which worker.py currently has no support for (a
    worker's `random` module is seeded exactly once, at bootstrap, from
    `WorkerConfig.global_random_seed`). Instead every worker's global random
    is seeded once, for the whole series, from one series-level seed. This
    only affects bots that read the bare `random` module directly for their
    own logic — dice, bet_history, outcomes, and stats are entirely
    unaffected (Task 9's in-process/isolated parity invariant for those still
    holds byte-for-byte).

    series_seed is `replay_seeds[0]` when replaying a recorded series (so
    replay reproduces the same worker RNG trajectory), else a fresh
    `secrets.randbits(64)` generated once per series.
    """
    series_seed = replay_seeds[0] if replay_seeds else secrets.randbits(64)

    return [
        WorkerConfig(
            spec.abs_file_path,
            spec.class_name,
            p.name,
            derive_worker_seed(series_seed, p.name),
            readmodel_name=readmodel_name,
        )
        for p, spec in zip(players, specs)
    ]


@dataclass
class SeriesResult:
    wins: dict[str, int]
    stats: GameStats
    perf: PerfTracker | None = None
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
    perf: PerfTracker | None = None,
    isolated: bool = True,
    worker_timeout_s: float = 5.0,
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
        isolated: If True (default), every player's algo() runs in its own
              subprocess worker (game/components/isolation/) for the whole
              series — one WorkerPool + ReadModelWriter built once, reused
              across all n_games games, and torn down when the series ends.
              Requires every player to have been loaded via
              import_player_classes_from_dir()/import_player_specs_from_dir()
              (see `_build_worker_configs`). If False, players run in-process
              exactly as before this task (legacy/debug path).
        worker_timeout_s: Per-turn wall-clock budget handed to WorkerPool when
              isolated=True. Placeholder value pending Task 13's perf spike,
              which tunes this for real; ignored when isolated=False.

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

    pool: WorkerPool | None = None
    writer: ReadModelWriter | None = None
    try:
        if isolated:
            # Validate BEFORE allocating any isolation resource (shared-memory
            # block, subprocesses) so a bad player list fails loudly without
            # leaking anything for the caller to clean up.
            specs = _require_isolation_specs(players)
            writer = ReadModelWriter(size_bytes=_readmodel_size_bytes(n_games, len(players)))
            configs = _build_worker_configs(players, specs, writer.name, replay_seeds)
            pool = WorkerPool(configs, timeout_s=worker_timeout_s)

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
                perf=perf,
                pool=pool,
                writer=writer,
            )
            wins[type(winner).__name__] += 1
            logger.info(f"Game {game_num}/{n_games}: {winner.name} wins")

            if on_game_complete is not None:
                on_game_complete(game_num, wins, stats)
    finally:
        if pool is not None:
            pool.close()
        if writer is not None:
            writer.close()
            writer.unlink()

    return SeriesResult(
        wins=wins,
        stats=stats,
        perf=perf,
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


def format_perf(tracker: PerfTracker, n_games: int) -> str:
    """Formats a PerfTracker's per-player timing (and optional memory) stats as a markdown table.

    Sorted slowest-first (by avg wall time) so outliers are easy to spot. Emitted as
    GFM table syntax (not a fixed-width chart) since plain-space column alignment
    collapses when this text is rendered by a markdown viewer. Cells are still padded
    for readability when read as raw, unrendered text.
    Returns "" if no calls were recorded.
    """
    players = tracker.tracked_players
    if not players:
        return ""

    memory_on = tracker.profile_memory

    headers = [
        "Player",
        "Calls",
        "TotalWall(s)",
        "TotalCPU(s)",
        "AvgWall(ms)",
        "P95Wall(ms)",
        "MaxWall(ms)",
        "AvgCPU(ms)",
        "MaxCPU(ms)",
    ]
    aligns = ["left"] + ["right"] * (len(headers) - 1)
    if memory_on:
        headers += ["AvgPeak(KB)", "MaxPeak(KB)"]
        aligns += ["right", "right"]

    ordered = sorted(players, key=lambda n: -tracker.avg_wall_ms(n))
    data_rows = []
    for name in ordered:
        cols = [
            name,
            str(tracker.call_count(name)),
            f"{tracker.total_wall_s(name):.3f}",
            f"{tracker.total_cpu_s(name):.3f}",
            f"{tracker.avg_wall_ms(name):.3f}",
            f"{tracker.p95_wall_ms(name):.3f}",
            f"{tracker.max_wall_ms(name):.3f}",
            f"{tracker.avg_cpu_ms(name):.3f}",
            f"{tracker.max_cpu_ms(name):.3f}",
        ]
        if memory_on:
            cols += [f"{tracker.avg_peak_kb(name):.1f}", f"{tracker.max_peak_kb(name):.1f}"]
        data_rows.append(cols)

    widths = [
        max(len(headers[i]), *(len(row[i]) for row in data_rows)) for i in range(len(headers))
    ]

    def _pad(cell: str, width: int, align: str) -> str:
        return cell.rjust(width) if align == "right" else cell.ljust(width)

    def _row(cols: list[str]) -> str:
        return "| " + " | ".join(_pad(c, w, a) for c, w, a in zip(cols, widths, aligns)) + " |"

    header_row = _row(headers)
    separator_row = (
        "| "
        + " | ".join(
            ("-" * w if a == "left" else "-" * (w - 1) + ":") for w, a in zip(widths, aligns)
        )
        + " |"
    )
    rows = [_row(cols) for cols in data_rows]

    lines = [
        f"\n=== Player Performance — {n_games} games ===\n",
        header_row,
        separator_row,
        *rows,
    ]
    return "\n".join(lines)
