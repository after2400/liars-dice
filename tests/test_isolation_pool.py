import os

from game.components.bets import Bet
from game.components.isolation import protocol as p
from game.components.isolation.pool import WorkerPool
from game.components.isolation.worker import WorkerConfig


def _ex(f):
    return os.path.abspath(f"examples/{f}")


NORMAL = WorkerConfig(_ex("always_bid_two_fives.py"), "AlwaysBidTwoFives", "t", b"\x00" * 32)
HANG = WorkerConfig(_ex("hangs_forever.py"), "HangsForever", "h", b"\x00" * 32)
TURN = ([1, 2, 3, 4, 5], None, 10, "L1", ["A"], 0)


def test_normal_call_returns_bet():
    with WorkerPool([NORMAL], timeout_s=5) as pool:
        assert isinstance(pool.call(0, TURN), Bet)


def test_infinite_loop_is_killed_and_penalised():
    with WorkerPool([HANG], timeout_s=1) as pool:
        assert pool.call(0, TURN) is p.WORKER_ERROR


def test_pool_still_usable_after_timeout_respawn():
    with WorkerPool([HANG, NORMAL], timeout_s=1) as pool:
        assert pool.call(0, TURN) is p.WORKER_ERROR  # HANG killed
        assert isinstance(pool.call(1, TURN), Bet)  # NORMAL still works
        assert pool.call(0, TURN) is p.WORKER_ERROR  # HANG respawned, hangs again
