"""Engine-internal per-player CPU/wall-time and (optional) memory instrumentation.

PerfTracker is never passed into a player's algo() — it's read only by
simulation callers (game/simulation/*.py), so no change to the AST import
allowlist in game/validate.py is needed.
"""

import math
import time
import tracemalloc
from collections import defaultdict
from contextlib import contextmanager


class PerfTracker:
    """Records per-player wall-clock time, CPU time, and (opt-in) peak memory.

    Pass `profile_memory=True` to also track tracemalloc peak-allocation bytes
    per call — this has real overhead, so it defaults to off.
    """

    def __init__(self, profile_memory: bool = False) -> None:
        self.profile_memory = profile_memory
        self._wall: dict[str, list[float]] = defaultdict(list)
        self._cpu: dict[str, list[float]] = defaultdict(list)
        self._peak_kb: dict[str, list[float]] = defaultdict(list)
        if profile_memory and not tracemalloc.is_tracing():
            tracemalloc.start()

    @contextmanager
    def time_call(self, player_name: str):
        """Times one algo() call. Records a sample even if the wrapped code
        raises — the finally block always runs before the exception propagates."""
        if self.profile_memory:
            # reset_peak() sets the peak watermark to the *current* traced
            # total, not zero — so we snapshot that baseline here and
            # subtract it below. Without this, peak_kb would include every
            # byte still alive in the process (GameStats, replay/bet
            # history, etc.) instead of just this call's own allocations.
            tracemalloc.reset_peak()
            baseline, _ = tracemalloc.get_traced_memory()
        t0_wall = time.perf_counter()
        t0_cpu = time.thread_time()
        try:
            yield
        finally:
            self._wall[player_name].append(time.perf_counter() - t0_wall)
            self._cpu[player_name].append(time.thread_time() - t0_cpu)
            if self.profile_memory:
                _, peak = tracemalloc.get_traced_memory()
                self._peak_kb[player_name].append((peak - baseline) / 1024)

    @property
    def tracked_players(self) -> list[str]:
        return sorted(self._wall.keys())

    def call_count(self, player_name: str) -> int:
        return len(self._wall.get(player_name, []))

    def total_wall_s(self, player_name: str) -> float:
        return sum(self._wall.get(player_name, []))

    def total_cpu_s(self, player_name: str) -> float:
        return sum(self._cpu.get(player_name, []))

    def avg_wall_ms(self, player_name: str) -> float:
        samples = self._wall.get(player_name, [])
        return (sum(samples) / len(samples) * 1000) if samples else 0.0

    def p95_wall_ms(self, player_name: str) -> float:
        return self._percentile_ms(self._wall.get(player_name, []), 0.95)

    def max_wall_ms(self, player_name: str) -> float:
        samples = self._wall.get(player_name, [])
        return max(samples) * 1000 if samples else 0.0

    def avg_cpu_ms(self, player_name: str) -> float:
        samples = self._cpu.get(player_name, [])
        return (sum(samples) / len(samples) * 1000) if samples else 0.0

    def max_cpu_ms(self, player_name: str) -> float:
        samples = self._cpu.get(player_name, [])
        return max(samples) * 1000 if samples else 0.0

    def avg_peak_kb(self, player_name: str) -> float | None:
        if not self.profile_memory:
            return None
        samples = self._peak_kb.get(player_name, [])
        return (sum(samples) / len(samples)) if samples else None

    def max_peak_kb(self, player_name: str) -> float | None:
        if not self.profile_memory:
            return None
        samples = self._peak_kb.get(player_name, [])
        return max(samples) if samples else None

    @staticmethod
    def _percentile_ms(samples: list[float], p: float) -> float:
        if not samples:
            return 0.0
        ordered = sorted(samples)
        idx = min(len(ordered) - 1, math.ceil(p * len(ordered)) - 1)
        return ordered[idx] * 1000
