import os

from game.components.isolation import protocol as p
from game.components.isolation.pool import WorkerPool
from game.components.isolation.worker import WorkerConfig

TURN = ([1, 1, 1, 1, 1], None, 5, "L1", ["A"], 0)


def test_worker_cannot_read_planted_secret(monkeypatch):
    # Parent has the secret; the worker must NOT.
    monkeypatch.setenv("GH_TOKEN", "super-secret-value")
    cfg = WorkerConfig(
        os.path.abspath("examples/reads_env_secret.py"), "ReadsEnvSecret", "probe", b"\x00" * 32
    )
    with WorkerPool([cfg], timeout_s=5) as pool:
        # The probe bot raises if it FAILS to find the secret and returns a bet if it DOES.
        # Isolation working => it never finds it => it raises => WORKER_ERROR.
        assert pool.call(0, TURN) is p.WORKER_ERROR


def test_c_call_hang_is_killed():
    from game.components.isolation import protocol as p
    from game.components.isolation.pool import WorkerPool
    from game.components.isolation.worker import WorkerConfig

    cfg = WorkerConfig(os.path.abspath("examples/hangs_in_c.py"), "HangsInC", "c", b"\x00" * 32)
    with WorkerPool([cfg], timeout_s=1) as pool:
        assert pool.call(0, ([1], None, 1, "L1", ["A"], 0)) is p.WORKER_ERROR
