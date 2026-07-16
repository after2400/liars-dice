"""Task 9 parity test: game_orchestrator's isolated path (pool + writer) must
produce an identical game to the legacy in-process path, given the same seed.

Uses examples/isolation_parity_liar_caller.py's ParityLiarCaller: a
deterministic v1 bot (open with a fixed 2x3 bid, otherwise call liar) so the
only variable between the two runs is *how* algo() is invoked, not what it
returns. This is a single-game test — it does not exercise the multi-game
shuffle-compounding scenario that makes pool-index-by-player-list-position
unsafe (see game_orchestrator's `pool` docstring and pool.py's
`name_to_index`); that requires a series of games (Task 10) to manifest.
"""

import os

from examples.isolation_parity_liar_caller import ParityLiarCaller
from game.components.isolation.pool import WorkerPool
from game.components.isolation.readmodel import ReadModelWriter
from game.components.isolation.seeding import derive_worker_seed
from game.components.isolation.worker import WorkerConfig
from game.components.script import game_orchestrator
from game.components.stats import GameStats

SEED = 42
PLAYER_FILE = os.path.abspath("examples/isolation_parity_liar_caller.py")


def _make_players():
    a = ParityLiarCaller()
    a.name = "A"
    b = ParityLiarCaller()
    b.name = "B"
    return [a, b]


def test_isolated_and_in_process_orchestrator_produce_identical_game():
    in_process_players = _make_players()
    in_process_bet_history: list[dict] = []
    in_process_outcomes: list[dict] = []
    in_process_stats = GameStats()

    in_process_winner = game_orchestrator(
        in_process_players,
        game_id=1,
        bet_history=in_process_bet_history,
        outcomes=in_process_outcomes,
        stats=in_process_stats,
        seed=SEED,
    )

    isolated_players = _make_players()
    isolated_bet_history: list[dict] = []
    isolated_outcomes: list[dict] = []
    isolated_stats = GameStats()

    configs = [
        WorkerConfig(
            player_file=PLAYER_FILE,
            player_class="ParityLiarCaller",
            name="A",
            global_random_seed=derive_worker_seed(SEED, "A"),
        ),
        WorkerConfig(
            player_file=PLAYER_FILE,
            player_class="ParityLiarCaller",
            name="B",
            global_random_seed=derive_worker_seed(SEED, "B"),
        ),
    ]

    writer = ReadModelWriter(size_bytes=1 << 20)
    try:
        with WorkerPool(configs, timeout_s=5) as pool:
            isolated_winner = game_orchestrator(
                isolated_players,
                game_id=1,
                bet_history=isolated_bet_history,
                outcomes=isolated_outcomes,
                stats=isolated_stats,
                seed=SEED,
                pool=pool,
                writer=writer,
            )
    finally:
        writer.close()
        writer.unlink()

    assert in_process_winner.name == isolated_winner.name

    assert len(in_process_bet_history) == len(isolated_bet_history)
    for expected, actual in zip(in_process_bet_history, isolated_bet_history):
        assert expected["game"] == actual["game"]
        assert expected["round"] == actual["round"]
        assert expected["player"] == actual["player"]
        assert expected["dice_count"] == actual["dice_count"]
        assert expected["bet"].quantity == actual["bet"].quantity
        assert expected["bet"].face == actual["bet"].face
        assert expected["bet"].player == actual["bet"].player

    assert len(in_process_outcomes) == len(isolated_outcomes)
    for expected, actual in zip(in_process_outcomes, isolated_outcomes):
        assert expected["round"] == actual["round"]
        assert expected["bidder"] == actual["bidder"]
        assert expected["challenger"] == actual["challenger"]
        assert expected["bet_held"] == actual["bet_held"]
        assert expected["loser"] == actual["loser"]
        assert dict(expected["hands"]) == dict(actual["hands"])
