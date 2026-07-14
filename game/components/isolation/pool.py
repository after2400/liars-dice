"""Parent-side manager for one isolated worker per player.

Owns spawn, per-turn request/response with a wall-clock timeout enforced by
external kill(), and respawn so a single misbehaving bot never wedges the series.
"""

import multiprocessing as mp

from game.components.isolation import protocol
from game.components.isolation.worker import WorkerConfig, worker_main

_CTX = mp.get_context("spawn")


class _Worker:
    def __init__(self, cfg: WorkerConfig):
        self.cfg = cfg
        self._spawn()

    def _spawn(self):
        self.parent_conn, child_conn = _CTX.Pipe()
        self.proc = _CTX.Process(target=worker_main, args=(child_conn, self.cfg), daemon=True)
        self.proc.start()
        self.parent_conn.recv()  # "ready"

    def kill_and_respawn(self):
        self.proc.kill()
        self.proc.join()
        self._spawn()

    def shutdown(self):
        try:
            self.parent_conn.send(None)
        except (BrokenPipeError, OSError):
            pass
        self.proc.join(timeout=1)
        if self.proc.is_alive():
            self.proc.kill()
            self.proc.join()


class WorkerPool:
    def __init__(self, configs: list[WorkerConfig], timeout_s: float):
        self.timeout_s = timeout_s
        self.workers = [_Worker(c) for c in configs]

    def call(self, index: int, turn: tuple):
        w = self.workers[index]
        try:
            w.parent_conn.send(turn)
            if not w.parent_conn.poll(self.timeout_s):
                w.kill_and_respawn()
                return protocol.WORKER_ERROR
            result = protocol.decode_result(w.parent_conn.recv_bytes())
        except (EOFError, OSError):
            w.kill_and_respawn()
            return protocol.WORKER_ERROR
        return result

    def close(self):
        for w in self.workers:
            w.shutdown()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
