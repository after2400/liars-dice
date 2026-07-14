"""Parent-side manager for one isolated worker per player.

Owns spawn, per-turn request/response with a wall-clock timeout enforced by
external kill(), and respawn so a single misbehaving bot never wedges the series.
"""

import multiprocessing as mp
import struct

from game.components.isolation import protocol
from game.components.isolation.worker import WorkerConfig, worker_main

_CTX = mp.get_context("spawn")


class _Worker:
    def __init__(self, cfg: WorkerConfig, timeout_s: float):
        self.cfg = cfg
        # Bootstrap-handshake budget. Reused from the pool's per-turn timeout: it's
        # already the "how long may one misbehaving bot stall us" budget the rest
        # of the pool enforces, and import + __init__ should comfortably fit
        # inside a single turn timeout, so a second knob isn't needed here.
        self.timeout_s = timeout_s
        self.ready = False
        self._spawn()

    def _spawn(self):
        self.ready = False
        self.parent_conn, child_conn = _CTX.Pipe()
        self.proc = _CTX.Process(target=worker_main, args=(child_conn, self.cfg), daemon=True)
        self.proc.start()
        # Close our (parent-side) copy of the child's pipe end now. If the child
        # dies before sending "ready" (exception at import time, exception in
        # __init__, etc.) this was the last reference to that write end held
        # outside the child process, so the child's exit closes it for good and
        # parent_conn.recv() raises EOFError immediately instead of blocking
        # forever waiting for a message that will never arrive.
        child_conn.close()
        try:
            # Bound the handshake so a bot that HANGS during bootstrap (rather
            # than crashing outright, e.g. an __init__ with `while True: pass`)
            # is also caught instead of wedging the pool forever.
            if not self.parent_conn.poll(self.timeout_s):
                self._kill_proc()
                return
            self.parent_conn.recv()  # "ready"
        except (EOFError, OSError):
            self._kill_proc()
            return
        self.ready = True

    def _kill_proc(self):
        try:
            self.proc.kill()
        except (ProcessLookupError, OSError):
            pass
        self.proc.join()

    def kill_and_respawn(self):
        self._kill_proc()
        self._spawn()

    def shutdown(self):
        if self.ready:
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
        self.workers = [_Worker(c, timeout_s) for c in configs]

    def call(self, index: int, turn: tuple):
        w = self.workers[index]
        if not w.ready:
            # Give a worker that failed to bootstrap exactly one respawn
            # attempt before penalising this call -- a transient failure
            # shouldn't permanently sideline the bot, but a bot that never
            # comes up must not hang or crash the caller either.
            w.kill_and_respawn()
            if not w.ready:
                return protocol.WORKER_ERROR
        try:
            w.parent_conn.send(turn)
            if not w.parent_conn.poll(self.timeout_s):
                w.kill_and_respawn()
                return protocol.WORKER_ERROR
            result = protocol.decode_result(w.parent_conn.recv_bytes())
        except (EOFError, OSError, struct.error):
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
