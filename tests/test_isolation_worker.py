import multiprocessing as mp

from game.components.bets import Bet
from game.components.isolation.worker import WorkerConfig, worker_main


def _run(cfg, turns):
    ctx = mp.get_context("spawn")
    parent, child = ctx.Pipe()
    proc = ctx.Process(target=worker_main, args=(child, cfg))
    proc.start()
    parent.recv()  # "ready"
    results = []
    for t in turns:
        parent.send(t)
        # worker replies via conn.send_bytes(protocol.encode_result(...)) — a raw,
        # struct-packed payload (see protocol.py), not a pickled object. It must be
        # read with recv_bytes(), not recv() (which unpickles and raises
        # UnpicklingError on raw bytes). The earlier "ready" handshake is a plain
        # pickled str sent via conn.send(...), so it correctly uses recv() above.
        results.append(parent.recv_bytes())
    parent.send(None)  # shutdown
    proc.join(timeout=5)
    return results


def test_worker_returns_encoded_bet(tmp_path):
    import os

    cfg = WorkerConfig(
        player_file=os.path.abspath("examples/always_bid_two_fives.py"),
        player_class="AlwaysBidTwoFives",
        name="t",
        global_random_seed=b"\x00" * 32,
    )
    # turn: hand, prior_bet, total_dice, tier, round_players, log_len
    [res] = _run(cfg, [([1, 2, 3, 4, 5], None, 10, "L1", ["A", "B"], 0)])
    from game.components.isolation import protocol as p

    out = p.decode_result(res)
    assert isinstance(out, Bet)


def test_worker_config_readmodel_name_defaults_to_none_for_positional_construction():
    """Existing positional call sites (older tests, pool.py) must keep working
    without knowing about the new field."""
    cfg = WorkerConfig("examples/always_bid_two_fives.py", "AlwaysBidTwoFives", "t", b"\x00" * 32)
    assert cfg.readmodel_name is None


def test_worker_reads_real_bet_history_and_outcomes_via_shared_readmodel():
    """End-to-end: a v2 (algo(self, ctx)) player running in an isolated worker
    sees real bet_history/outcomes entries from a ReadModelWriter the parent
    populated, wired through WorkerConfig.readmodel_name -> worker_main ->
    ReadModelReader -> _build_args (Task 6)."""
    import os

    from game.components.isolation.readmodel import ReadModelWriter

    w = ReadModelWriter(size_bytes=1 << 20)
    try:
        w.append_bet(
            {
                "game": 1,
                "round": 0,
                "player": "A",
                "bet": Bet(2, 3, "A"),
                "dice_count": 5,
            }
        )
        w.append_bet(
            {
                "game": 1,
                "round": 0,
                "player": "B",
                "bet": Bet(3, 4, "B"),
                "dice_count": 5,
            }
        )
        w.append_outcome(
            {
                "game": 1,
                "round": -1,
                "hands": {"A": (1, 2, 3, 4, 5)},
                "final_bet": Bet(1, 1, "A"),
                "bidder": "A",
                "challenger": "B",
                "bet_held": True,
                "loser": "B",
            }
        )

        cfg = WorkerConfig(
            player_file=os.path.abspath("examples/reports_readmodel_lengths.py"),
            player_class="ReportsReadmodelLengths",
            name="r",
            global_random_seed=b"\x00" * 32,
            readmodel_name=w.name,
        )
        # log_len=2: this turn should see both bet_history entries appended above.
        [res] = _run(cfg, [([1, 2, 3, 4, 5], None, 10, "L1", ["A", "B"], 2)])
        from game.components.isolation import protocol as p

        out = p.decode_result(res)
        assert isinstance(out, Bet)
        # ReportsReadmodelLengths encodes quantity=len(bet_history), face=1+len(outcomes)%6
        assert out.quantity == 2
        assert out.face == 2  # 1 outcome -> 1 + (1 % 6) == 2
    finally:
        w.close()
        w.unlink()


def test_worker_v2_bot_sees_real_stats_via_shared_readmodel():
    """End-to-end: a v2 (algo(self, ctx)) player running in an isolated worker
    sees a real GameStats snapshot the parent published via
    ReadModelWriter.publish_stats, wired through WorkerConfig.readmodel_name ->
    worker_main -> ReadModelReader.stats_view() -> _build_args (Task 7)."""
    import os

    from game.components.isolation.readmodel import ReadModelWriter
    from game.components.stats import GameStats

    w = ReadModelWriter(size_bytes=1 << 20)
    try:
        stats = GameStats()
        stats.start_game(["Alice", "Bob", "Carol"])
        w.publish_stats(stats)

        cfg = WorkerConfig(
            player_file=os.path.abspath("examples/reports_stats_view.py"),
            player_class="ReportsStatsView",
            name="s",
            global_random_seed=b"\x00" * 32,
            readmodel_name=w.name,
        )
        [res] = _run(cfg, [([1, 2, 3, 4, 5], None, 10, "L1", ["A", "B"], 0)])
        from game.components.isolation import protocol as p

        out = p.decode_result(res)
        assert isinstance(out, Bet)
        # ReportsStatsView encodes quantity=len(ctx.stats.dice_counts); start_game
        # seeded 3 players.
        assert out.quantity == 3
    finally:
        w.close()
        w.unlink()
