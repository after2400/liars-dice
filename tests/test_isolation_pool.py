import os
import time

from game.components.bets import Bet
from game.components.isolation import protocol as p
from game.components.isolation.pool import WorkerPool
from game.components.isolation.worker import WorkerConfig


def _ex(f):
    return os.path.abspath(f"examples/{f}")


NORMAL = WorkerConfig(_ex("always_bid_two_fives.py"), "AlwaysBidTwoFives", "t", b"\x00" * 32)
HANG = WorkerConfig(_ex("hangs_forever.py"), "HangsForever", "h", b"\x00" * 32)
CRASHES_AT_IMPORT = WorkerConfig(_ex("crashes_at_import.py"), "CrashesAtImport", "c", b"\x00" * 32)
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


def test_bootstrap_crash_does_not_hang_pool_construction():
    # Regression test: a bot that raises at import time used to hang the pool
    # forever, because the parent kept its own copy of the child's pipe end
    # open, so recv() never saw EOF. Hard wall-clock guard so a regression
    # fails fast instead of hanging CI.
    start = time.monotonic()
    with WorkerPool([CRASHES_AT_IMPORT], timeout_s=2) as pool:
        construct_elapsed = time.monotonic() - start
        assert construct_elapsed < 5, "pool construction hung on a crashing bootstrap"

        assert pool.call(0, TURN) is p.WORKER_ERROR
        total_elapsed = time.monotonic() - start
        assert total_elapsed < 10, "call() on a never-ready worker hung"


def test_bootstrap_crash_does_not_wedge_other_workers():
    # A bad bootstrap in one slot must not prevent a healthy worker elsewhere
    # in the same pool from running normally.
    start = time.monotonic()
    with WorkerPool([CRASHES_AT_IMPORT, NORMAL], timeout_s=2) as pool:
        assert pool.call(0, TURN) is p.WORKER_ERROR
        assert isinstance(pool.call(1, TURN), Bet)
        assert time.monotonic() - start < 10, "mixed pool with a bad bootstrap hung"
