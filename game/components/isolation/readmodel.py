"""Read-only shared-memory read-model handed to isolated player workers.

Gives an isolated worker O(1)-per-turn access to the game's bet history and
round outcomes without marshalling growing state across the process boundary
on every turn: the parent (`ReadModelWriter`) appends into one
`multiprocessing.shared_memory.SharedMemory` block; each worker
(`ReadModelReader`) maps that block once at startup and answers
`bet_history_view(log_len)` / `outcomes_view()` with direct offset lookups —
no scan, no copy of prior entries.

Read-only mechanism (spike-confirmed, see Task 6 report for full spike output):
`memoryview(shm.buf).toreadonly()` is a Python-level guard only — it blocks
writes made *through that specific memoryview*, but the underlying `shm.buf`
handle it wraps stays fully writable, so any code that reaches `shm.buf`
another way (or never goes through `.toreadonly()`) can still mutate the
block. The spike confirmed re-opening the block's fd with
`mmap.mmap(shm._fd, size, prot=mmap.PROT_READ)` gives a true OS-enforced
read-only mapping: writes through it raise `TypeError` at the syscall/mmap
level, not just at a Python wrapper level. `ReadModelReader` uses that path
exclusively and never touches the writable `shm.buf` at all. `SharedMemory._fd`
is a private attribute, POSIX-only (this project targets POSIX per
CLAUDE.md — darwin/linux); if a future CPython removes it we raise a clear
`RuntimeError` rather than silently falling back to a weaker guard.

The spike also measured latency: 10k fixed-size record append/read came to
~0.1us per record (struct.pack_into / unpack_from directly against a shared
buffer) — negligible next to a single game's history (tens to low hundreds
of entries), confirming per-turn cost stays O(1) regardless of history length.

Layout: a small fixed header (magic, logical size_bytes, bet_count,
outcome_count, outcome_data_write_pos) followed by three regions whose
boundaries are a pure function of `size_bytes` (computed identically by
writer and reader — nothing but `size_bytes` itself needs to travel with the
block name):

  - bet region: fixed-field records (`game`, `round`, `player` name,
    `bet.quantity`, `bet.face`, `dice_count`) addressed directly by
    `offset = region_start + index * RECORD_SIZE` — no index table needed
    since every record is the same size. `bet_history` entries from
    `script.py` are fixed-shape, so this fits without a pickle fallback.
  - outcome index: an array of uint32 byte-offsets into the outcome data
    region, one per outcome, appended alongside each outcome.
  - outcome data: length-prefixed pickled blobs. `script.py`'s outcome
    entries are NOT fixed-shape (`hands` is a dict keyed by however many
    players are still active, each value a variable-length dice tuple), so
    outcomes use the pickled-blob fallback the brief anticipated.

Publish ordering (parent never lets a reader observe a half-written entry):
payload bytes are written first, then the count field that makes them
visible is bumped last. Readers only ever trust index `< count`.

`outcomes_view()` deliberately takes no `log_len`-style parameter, unlike
`bet_history_view(log_len)`. This is safe under this design's synchronous
invariant, not an oversight: `WorkerPool.call()` is a blocking one-turn-at-a-
time request/response (see `pool.py`), and `game_orchestrator` (script.py)
only appends a new bet_history/outcome entry *after* it has already used the
previous turn's response, before dispatching the next turn. So whatever is
published in shared memory at the moment a turn is dispatched to a worker is
already exactly "history up to and not including this turn" for both
bet_history and outcomes — there is no concurrent writer that could publish a
"future" entry mid-turn. `bet_history_view` still takes `log_len` because
that value already existed on the turn tuple (6th field) before this task;
honoring it directly is a stronger, self-contained guarantee that doesn't
depend on that invariant. If a future change makes turn dispatch concurrent
across players *within the same game* (not just across games/pools), this
invariant would break and `outcomes_view` would need an equivalent explicit
bound — flagged here for whoever wires the parent side (Task 7).

GameStats channel (Task 7): a separate double-buffered region, added
alongside the bet/outcome regions in the same block. `publish_stats` pickles
`GameStats.snapshot_state()` (a plain-dict deep-copy — see stats.py; the raw
backing stores include `defaultdict(lambda: ...)` factories that are not
picklable) and writes it into whichever of the two stats buffers is
currently NOT the one readers are pointed at, then flips a single
`stats_active` header field (0 or 1) to that buffer LAST — same
write-payload-then-publish-visibility ordering as the bet/outcome regions.
A reader captures `stats_active` once, reads that buffer's length and bytes,
and never touches the other buffer, so it can never observe a torn write
even if the parent starts a new publish (into the now-unreferenced buffer)
while the read is in flight. This relies on the same synchronous
one-turn-at-a-time dispatch invariant described above for `outcomes_view`
(at most one publish happens between the moment a reader captures
`stats_active` and the moment it finishes reading that buffer) — under
concurrent-within-a-game dispatch this would need real generation counters
or locking, not just two buffers.
"""

from __future__ import annotations

import mmap
import pickle
import struct
from dataclasses import dataclass
from multiprocessing import shared_memory
from types import MappingProxyType

from game.components.bets import Bet
from game.components.stats import GameStats

_MAGIC = b"LDR1"
# magic, size_bytes, bet_count, outcome_count, outcome_write_pos,
# stats_active (0 or 1), stats_len0, stats_len1
_HEADER_FMT = "<4sIIIIIII"
_HEADER_SIZE = struct.calcsize(_HEADER_FMT)

# Byte offsets of individual header fields (all little-endian uint32, after the
# 4-byte magic) — used by the writer's targeted single-field publishes below.
_OFF_BET_COUNT = 4 + 4
_OFF_OUTCOME_COUNT = _OFF_BET_COUNT + 4
_OFF_OUTCOME_WRITE_POS = _OFF_OUTCOME_COUNT + 4
_OFF_STATS_ACTIVE = _OFF_OUTCOME_WRITE_POS + 4
_OFF_STATS_LEN0 = _OFF_STATS_ACTIVE + 4
_OFF_STATS_LEN1 = _OFF_STATS_LEN0 + 4

_NAME_FIELD_SIZE = 128  # bytes; MAX_NAME_LEN (game/validate.py) is 25 chars, up to 4
# bytes/char in UTF-8 worst case (~100 bytes) — 128 leaves headroom without being wasteful.
_BET_FMT = f"<II{_NAME_FIELD_SIZE}sIII"  # game, round, player, quantity, face, dice_count
_BET_RECORD_SIZE = struct.calcsize(_BET_FMT)

_BET_REGION_FRACTION = 0.5
_OUTCOME_INDEX_FRACTION = 0.1
_STATS_REGION_FRACTION = 0.2  # split evenly into two double-buffer halves
# remainder of the block (after header + bet region + outcome index + stats
# double-buffer) is outcome data.


@dataclass(frozen=True)
class _Layout:
    bet_capacity: int
    bet_region_offset: int
    outcome_capacity: int
    outcome_index_offset: int
    outcome_data_offset: int
    outcome_data_capacity: int
    stats_buffer_capacity: int
    stats_buf0_offset: int
    stats_buf1_offset: int


def _compute_layout(size_bytes: int) -> _Layout:
    """Pure function of `size_bytes` — writer and reader call this identically
    so no extra offsets need to be transmitted alongside the block name."""
    usable = size_bytes - _HEADER_SIZE
    if usable <= 0:
        raise ValueError(f"size_bytes={size_bytes} too small to hold the read-model header")

    bet_region_bytes = int(usable * _BET_REGION_FRACTION)
    bet_capacity = bet_region_bytes // _BET_RECORD_SIZE
    bet_region_bytes = bet_capacity * _BET_RECORD_SIZE  # trim to a whole number of records

    outcome_index_budget = int(usable * _OUTCOME_INDEX_FRACTION)
    outcome_capacity = outcome_index_budget // 4
    outcome_index_bytes = outcome_capacity * 4

    stats_region_budget = int(usable * _STATS_REGION_FRACTION)
    stats_buffer_capacity = stats_region_budget // 2
    stats_region_bytes = stats_buffer_capacity * 2  # trim to two equal halves

    outcome_data_capacity = usable - bet_region_bytes - outcome_index_bytes - stats_region_bytes

    if bet_capacity < 1 or outcome_capacity < 1 or outcome_data_capacity < 64:
        raise ValueError(
            f"size_bytes={size_bytes} too small for a usable read-model block "
            f"(got bet_capacity={bet_capacity}, outcome_capacity={outcome_capacity}, "
            f"outcome_data_capacity={outcome_data_capacity})"
        )

    bet_region_offset = _HEADER_SIZE
    outcome_index_offset = bet_region_offset + bet_region_bytes
    outcome_data_offset = outcome_index_offset + outcome_index_bytes
    stats_buf0_offset = outcome_data_offset + outcome_data_capacity
    stats_buf1_offset = stats_buf0_offset + stats_buffer_capacity
    return _Layout(
        bet_capacity=bet_capacity,
        bet_region_offset=bet_region_offset,
        outcome_capacity=outcome_capacity,
        outcome_index_offset=outcome_index_offset,
        outcome_data_offset=outcome_data_offset,
        outcome_data_capacity=outcome_data_capacity,
        stats_buffer_capacity=stats_buffer_capacity,
        stats_buf0_offset=stats_buf0_offset,
        stats_buf1_offset=stats_buf1_offset,
    )


def _plain(obj):
    """Recursively convert MappingProxyType -> dict so pickle can serialize it.

    script.py's real outcome entries (and their nested `hands` field) are
    MappingProxyType, which is not picklable in this Python version. Callers
    of append_outcome may pass either raw script.py entries or already-plain
    dicts (as the tests do); this makes both work.
    """
    if isinstance(obj, (dict, MappingProxyType)):
        return {k: _plain(v) for k, v in obj.items()}
    return obj


class ReadModelWriter:
    """Parent-side handle: owns the shared_memory block and appends entries.

    Not thread/process-safe for concurrent writers — exactly one writer
    (the game orchestrator) is expected per block, matching one block per
    game. Readers (isolated workers) only ever read.
    """

    def __init__(self, size_bytes: int):
        self._layout = _compute_layout(size_bytes)
        self._shm = shared_memory.SharedMemory(create=True, size=size_bytes)
        # Pin the LOGICAL size_bytes into the header (not self._shm.size, which the
        # OS may round up to a page boundary) so the reader recomputes the exact
        # same region layout from it. stats_active/stats_len0/stats_len1 all start
        # at 0 — no stats have been published yet; stats_view() treats
        # length-0-on-buffer-0 as "nothing published, return an empty GameStats".
        struct.pack_into(_HEADER_FMT, self._shm.buf, 0, _MAGIC, size_bytes, 0, 0, 0, 0, 0, 0)
        self.name = self._shm.name

    # -- header helpers (writer keeps its own buf handle; it's the sole writer) --
    def _read_counts(self):
        _, _, bet_count, outcome_count, outcome_write_pos, _active, _len0, _len1 = (
            struct.unpack_from(_HEADER_FMT, self._shm.buf, 0)
        )
        return bet_count, outcome_count, outcome_write_pos

    def _read_stats_header(self):
        _, _, _bet_count, _outcome_count, _write_pos, active, len0, len1 = struct.unpack_from(
            _HEADER_FMT, self._shm.buf, 0
        )
        return active, len0, len1

    def _publish_bet_count(self, count: int) -> None:
        struct.pack_into("<I", self._shm.buf, _OFF_BET_COUNT, count)

    def _publish_outcome_count(self, count: int) -> None:
        struct.pack_into("<I", self._shm.buf, _OFF_OUTCOME_COUNT, count)

    def _publish_outcome_write_pos(self, pos: int) -> None:
        struct.pack_into("<I", self._shm.buf, _OFF_OUTCOME_WRITE_POS, pos)

    def _publish_stats_len(self, buffer_idx: int, length: int) -> None:
        offset = _OFF_STATS_LEN0 if buffer_idx == 0 else _OFF_STATS_LEN1
        struct.pack_into("<I", self._shm.buf, offset, length)

    def _publish_stats_active(self, buffer_idx: int) -> None:
        struct.pack_into("<I", self._shm.buf, _OFF_STATS_ACTIVE, buffer_idx)

    def append_bet(self, entry: dict) -> None:
        bet_count, _outcome_count, _write_pos = self._read_counts()
        if bet_count >= self._layout.bet_capacity:
            raise BufferError(
                "ReadModelWriter: bet history capacity exhausted "
                f"({self._layout.bet_capacity} records) — allocate a larger size_bytes"
            )
        bet: Bet = entry["bet"]
        name_bytes = entry["player"].encode("utf-8")
        if len(name_bytes) > _NAME_FIELD_SIZE:
            raise ValueError(
                f"player name {entry['player']!r} ({len(name_bytes)} bytes) exceeds the "
                f"{_NAME_FIELD_SIZE}-byte read-model name field"
            )
        offset = self._layout.bet_region_offset + bet_count * _BET_RECORD_SIZE
        struct.pack_into(
            _BET_FMT,
            self._shm.buf,
            offset,
            entry["game"],
            entry["round"],
            name_bytes,
            bet.quantity,
            bet.face,
            entry["dice_count"],
        )
        self._publish_bet_count(bet_count + 1)  # publish LAST — payload is already in place

    def append_outcome(self, entry: dict) -> None:
        _bet_count, outcome_count, write_pos = self._read_counts()
        if outcome_count >= self._layout.outcome_capacity:
            raise BufferError(
                "ReadModelWriter: outcome capacity exhausted "
                f"({self._layout.outcome_capacity} records) — allocate a larger size_bytes"
            )
        blob = pickle.dumps(_plain(entry), protocol=pickle.HIGHEST_PROTOCOL)
        needed = 4 + len(blob)
        if write_pos + needed > self._layout.outcome_data_capacity:
            raise BufferError(
                "ReadModelWriter: outcome data region exhausted "
                f"({self._layout.outcome_data_capacity} bytes) — allocate a larger size_bytes"
            )
        data_offset = self._layout.outcome_data_offset + write_pos
        struct.pack_into("<I", self._shm.buf, data_offset, len(blob))
        self._shm.buf[data_offset + 4 : data_offset + 4 + len(blob)] = blob

        index_offset = self._layout.outcome_index_offset + outcome_count * 4
        struct.pack_into("<I", self._shm.buf, index_offset, write_pos)

        self._publish_outcome_write_pos(write_pos + needed)
        self._publish_outcome_count(outcome_count + 1)  # publish LAST

    def publish_stats(self, stats: GameStats) -> None:
        """Double-buffered publish of a `GameStats` snapshot.

        Writes into whichever of the two stats buffers is currently NOT the
        active one, then flips `stats_active` LAST — so a reader that already
        captured the old active index keeps reading the untouched buffer, and
        a reader that reads after this call sees the new snapshot in full.
        Never torn under the one-publish-per-turn / synchronous-dispatch
        invariant documented in the module docstring.
        """
        active, _len0, _len1 = self._read_stats_header()
        target = 1 - active
        blob = pickle.dumps(stats.snapshot_state(), protocol=pickle.HIGHEST_PROTOCOL)
        capacity = self._layout.stats_buffer_capacity
        if len(blob) > capacity:
            raise BufferError(
                f"ReadModelWriter: stats snapshot ({len(blob)} bytes) exceeds the "
                f"{capacity}-byte stats double-buffer capacity — allocate a larger size_bytes"
            )
        offset = self._layout.stats_buf0_offset if target == 0 else self._layout.stats_buf1_offset
        self._shm.buf[offset : offset + len(blob)] = blob
        self._publish_stats_len(target, len(blob))
        self._publish_stats_active(target)  # flip LAST — payload is already in place

    def close(self) -> None:
        self._shm.close()

    def unlink(self) -> None:
        self._shm.unlink()


class _BetHistoryView:
    """`_ReadOnlySequence`-compatible read-only view over the bet region."""

    __slots__ = ("_mmap", "_layout", "_n")

    def __init__(self, ro_mmap: mmap.mmap, layout: _Layout, n: int) -> None:
        self._mmap = ro_mmap
        self._layout = layout
        self._n = n

    def __len__(self) -> int:
        return self._n

    def _entry_at(self, i: int) -> MappingProxyType:
        offset = self._layout.bet_region_offset + i * _BET_RECORD_SIZE
        game, round_, name_raw, quantity, face, dice_count = struct.unpack_from(
            _BET_FMT, self._mmap, offset
        )
        player = name_raw.rstrip(b"\x00").decode("utf-8")
        return MappingProxyType(
            {
                "game": game,
                "round": round_,
                "player": player,
                "bet": Bet(quantity, face, player),
                "dice_count": dice_count,
            }
        )

    def __getitem__(self, idx: int) -> MappingProxyType:
        if idx < 0:
            idx += self._n
        if not (0 <= idx < self._n):
            raise IndexError("bet history index out of range")
        return self._entry_at(idx)

    def __iter__(self):
        for i in range(self._n):
            yield self._entry_at(i)

    def __repr__(self) -> str:
        return f"_BetHistoryView(len={self._n})"


class _OutcomesView:
    """`_ReadOnlySequence`-compatible read-only view over the outcomes region."""

    __slots__ = ("_mmap", "_layout", "_n")

    def __init__(self, ro_mmap: mmap.mmap, layout: _Layout, n: int) -> None:
        self._mmap = ro_mmap
        self._layout = layout
        self._n = n

    def __len__(self) -> int:
        return self._n

    def _entry_at(self, i: int) -> MappingProxyType:
        (rel_offset,) = struct.unpack_from(
            "<I", self._mmap, self._layout.outcome_index_offset + i * 4
        )
        data_offset = self._layout.outcome_data_offset + rel_offset
        (length,) = struct.unpack_from("<I", self._mmap, data_offset)
        blob = bytes(self._mmap[data_offset + 4 : data_offset + 4 + length])
        data = pickle.loads(blob)
        if "hands" in data:
            data["hands"] = MappingProxyType(data["hands"])
        return MappingProxyType(data)

    def __getitem__(self, idx: int) -> MappingProxyType:
        if idx < 0:
            idx += self._n
        if not (0 <= idx < self._n):
            raise IndexError("outcomes index out of range")
        return self._entry_at(idx)

    def __iter__(self):
        for i in range(self._n):
            yield self._entry_at(i)

    def __repr__(self) -> str:
        return f"_OutcomesView(len={self._n})"


class ReadModelReader:
    """Child-side handle: maps the block read-only and answers turn-scoped views."""

    def __init__(self, name: str):
        # Open once with the normal (writable-by-default) handle purely to read the
        # header and obtain the fd — we never read/write through self._shm.buf itself.
        self._shm = shared_memory.SharedMemory(name=name)
        magic, size_bytes, _bet_count, _outcome_count, _write_pos, _active, _len0, _len1 = (
            struct.unpack_from(_HEADER_FMT, self._shm.buf, 0)
        )
        if magic != _MAGIC:
            raise ValueError(f"shared memory block {name!r} is not a valid read-model block")
        self._layout = _compute_layout(size_bytes)
        try:
            fd = self._shm._fd  # noqa: SLF001 — see module docstring: spike-confirmed,
            # this is the only way to get a true OS-enforced read-only mapping.
        except AttributeError as e:  # pragma: no cover - defensive, not expected on POSIX
            raise RuntimeError(
                "ReadModelReader requires multiprocessing.shared_memory.SharedMemory._fd "
                "(POSIX-only, private) to open a read-only mapping; this CPython build "
                "does not expose it."
            ) from e
        self._ro_mmap = mmap.mmap(fd, self._shm.size, prot=mmap.PROT_READ)

    def _read_header(self):
        return struct.unpack_from(_HEADER_FMT, self._ro_mmap, 0)

    def bet_history_view(self, log_len: int) -> _BetHistoryView:
        _magic, _size, bet_count, _outcome_count, _write_pos, _active, _len0, _len1 = (
            self._read_header()
        )
        n = bet_count if log_len is None else min(log_len, bet_count)
        return _BetHistoryView(self._ro_mmap, self._layout, n)

    def outcomes_view(self) -> _OutcomesView:
        # No log_len: safe under the synchronous turn-dispatch invariant documented
        # in the module docstring. Whatever is published here is already exactly
        # "history up to and not including this turn."
        _magic, _size, _bet_count, outcome_count, _write_pos, _active, _len0, _len1 = (
            self._read_header()
        )
        return _OutcomesView(self._ro_mmap, self._layout, outcome_count)

    def stats_view(self) -> GameStats:
        """Reconstruct a `GameStats` from whichever stats buffer is currently
        active. Reads `stats_active` once, then only that buffer's length and
        bytes — see the module docstring's "GameStats channel" section for why
        this can't observe a torn write under this design's invariants.
        """
        _magic, _size, _bet_count, _outcome_count, _write_pos, active, len0, len1 = (
            self._read_header()
        )
        length = len0 if active == 0 else len1
        if length == 0:
            # Nothing published yet (worker started before the parent's first
            # publish_stats call) — an empty GameStats mirrors GameContext's own
            # "stats=None -> GameStats()" default.
            return GameStats()
        offset = self._layout.stats_buf0_offset if active == 0 else self._layout.stats_buf1_offset
        blob = bytes(self._ro_mmap[offset : offset + length])
        return GameStats.restore_state(pickle.loads(blob))

    def close(self) -> None:
        self._ro_mmap.close()
        self._shm.close()
