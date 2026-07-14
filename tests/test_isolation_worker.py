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
