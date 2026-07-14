import multiprocessing as mp
from types import MappingProxyType

import pytest

from game.components.bets import Bet
from game.components.isolation.readmodel import ReadModelReader, ReadModelWriter

_CTX = mp.get_context("spawn")


def test_bet_entries_roundtrip_through_shared_memory():
    w = ReadModelWriter(size_bytes=1 << 20)
    try:
        w.append_bet(
            {
                "game": 1,
                "round": 2,
                "player": "Alice",
                "bet": Bet(3, 5, "Alice"),
                "dice_count": 4,
            }
        )
        r = ReadModelReader(w.name)
        view = r.bet_history_view(log_len=1)
        assert len(view) == 1
        entry = view[0]
        assert isinstance(entry, MappingProxyType)
        assert entry["player"] == "Alice"
        assert (entry["bet"].quantity, entry["bet"].face) == (3, 5)
        r.close()
    finally:
        w.close()
        w.unlink()


def test_multiple_bet_entries_addressed_independently():
    w = ReadModelWriter(size_bytes=1 << 20)
    try:
        for i in range(5):
            w.append_bet(
                {
                    "game": 1,
                    "round": i,
                    "player": f"P{i}",
                    "bet": Bet(i + 1, (i % 6) + 1, f"P{i}"),
                    "dice_count": 5,
                }
            )
        r = ReadModelReader(w.name)
        view = r.bet_history_view(log_len=5)
        assert len(view) == 5
        for i in range(5):
            entry = view[i]
            assert entry["player"] == f"P{i}"
            assert entry["round"] == i
            assert entry["bet"].quantity == i + 1
        # negative indexing, like a live list
        assert view[-1]["player"] == "P4"
        r.close()
    finally:
        w.close()
        w.unlink()


def test_bet_history_view_honors_log_len_clipping():
    """A turn dispatched when only N bets exist so far must not see later bets
    even if more have since been appended to the block (defense in depth for
    the synchronous-dispatch invariant this design relies on)."""
    w = ReadModelWriter(size_bytes=1 << 20)
    try:
        for i in range(3):
            w.append_bet(
                {
                    "game": 1,
                    "round": 0,
                    "player": f"P{i}",
                    "bet": Bet(1, 2, f"P{i}"),
                    "dice_count": 5,
                }
            )
        r = ReadModelReader(w.name)
        view = r.bet_history_view(log_len=1)
        assert len(view) == 1
        assert view[0]["player"] == "P0"
        with pytest.raises(IndexError):
            view[1]
        r.close()
    finally:
        w.close()
        w.unlink()


def test_outcome_entries_roundtrip_with_variable_hands():
    w = ReadModelWriter(size_bytes=1 << 20)
    try:
        w.append_outcome(
            {
                "game": 1,
                "round": 1,
                "hands": {"Alice": (1, 2, 3, 4, 5), "Bob": (6, 6, 6)},
                "final_bet": Bet(3, 5, "Alice"),
                "bidder": "Alice",
                "challenger": "Bob",
                "bet_held": True,
                "loser": "Bob",
            }
        )
        r = ReadModelReader(w.name)
        view = r.outcomes_view()
        assert len(view) == 1
        entry = view[0]
        assert isinstance(entry, MappingProxyType)
        assert isinstance(entry["hands"], MappingProxyType)
        assert entry["hands"]["Alice"] == (1, 2, 3, 4, 5)
        assert entry["final_bet"].quantity == 3
        assert entry["loser"] == "Bob"
        r.close()
    finally:
        w.close()
        w.unlink()


def test_bet_capacity_exhaustion_raises_buffer_error():
    # A tiny block leaves room for only a couple of fixed-size bet records.
    w = ReadModelWriter(size_bytes=1024)
    try:
        with pytest.raises(BufferError):
            for i in range(1000):
                w.append_bet(
                    {
                        "game": 1,
                        "round": 0,
                        "player": "P",
                        "bet": Bet(1, 2, "P"),
                        "dice_count": 5,
                    }
                )
    finally:
        w.close()
        w.unlink()


def _child_attempts_write(name, result_q):
    r = ReadModelReader(name)
    try:
        r._ro_mmap[0:1] = b"\x99"
        result_q.put("write_succeeded")
    except TypeError:
        result_q.put("write_blocked")
    finally:
        r.close()


def test_child_process_cannot_mutate_shared_block_through_reader():
    w = ReadModelWriter(size_bytes=1 << 20)
    try:
        w.append_bet(
            {
                "game": 1,
                "round": 0,
                "player": "Alice",
                "bet": Bet(3, 5, "Alice"),
                "dice_count": 4,
            }
        )
        q = _CTX.Queue()
        p = _CTX.Process(target=_child_attempts_write, args=(w.name, q))
        p.start()
        result = q.get(timeout=10)
        p.join(timeout=10)
        assert result == "write_blocked"

        # parent's data must be untouched by the child's attempted write
        r = ReadModelReader(w.name)
        entry = r.bet_history_view(log_len=1)[0]
        assert entry["player"] == "Alice"
        r.close()
    finally:
        w.close()
        w.unlink()
