import multiprocessing as mp
import shutil
from pathlib import Path
from types import MappingProxyType

import pytest

from game.components.bets import Bet
from game.components.isolation.readmodel import ReadModelReader, ReadModelWriter
from game.components.series import run_series
from game.components.utils import import_player_classes_from_dir

_CTX = mp.get_context("spawn")
_DEEPTHOUGHT_SRC = Path(__file__).resolve().parent.parent / "players" / "deepthought.py"

_OPPONENT_SRC = """
from game.components.bets import Bet


class SimpleCaller:
    name = "Simple Caller"

    def algo(self, ctx):
        # Fixed open, then always call liar -- deterministic opponent so any
        # game-outcome variance across the 3-game series traces back to
        # DeepThought's own (real, non-deterministic) EV logic, not the
        # opponent.
        if ctx.prior_bet is None:
            return Bet(2, 3, self.name)
        return None
"""


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


def test_bet_history_view_supports_slicing():
    """Regression for Task 14: real PRM bots (deepthought.py, ripley.py,
    evilstewie.py, merovingian.py) use the `history[self._history_seen :]`
    open-ended-slice idiom on ctx.bet_history. Under isolation this used to
    raise TypeError on every turn (slice doesn't support `<`), so these bots
    lost every round via the except-Exception penalty path. Compare against
    a plain-list oracle built from the same entries."""
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
        oracle = [view[i] for i in range(5)]  # plain-list oracle via known-good int path

        def players(seq):
            return [e["player"] for e in seq]

        for sl in (slice(2, None), slice(-2, None), slice(None, -1), slice(1, 3)):
            result = view[sl]
            assert isinstance(result, list)
            assert players(result) == players(oracle[sl])
            assert len(result) == len(oracle[sl])

        # empty slice
        assert view[10:] == []
        # every entry is still an immutable MappingProxyType
        for entry in view[1:3]:
            assert isinstance(entry, MappingProxyType)
        r.close()
    finally:
        w.close()
        w.unlink()


def test_outcomes_view_supports_slicing():
    w = ReadModelWriter(size_bytes=1 << 20)
    try:
        for i in range(4):
            w.append_outcome(
                {
                    "game": 1,
                    "round": i,
                    "hands": {"Alice": (1, 2, 3), "Bob": (4, 5)},
                    "final_bet": Bet(2 + i, 3, "Alice"),
                    "bidder": "Alice",
                    "challenger": "Bob",
                    "bet_held": i % 2 == 0,
                    "loser": "Bob" if i % 2 == 0 else "Alice",
                }
            )
        r = ReadModelReader(w.name)
        view = r.outcomes_view()
        oracle = [view[i] for i in range(4)]

        def rounds(seq):
            return [e["round"] for e in seq]

        for sl in (slice(2, None), slice(-2, None), slice(None, -1), slice(1, 3)):
            result = view[sl]
            assert isinstance(result, list)
            assert rounds(result) == rounds(oracle[sl])
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


def test_real_bot_using_history_slice_idiom_not_penalized_every_turn_under_isolation(tmp_path):
    """End-to-end regression for Task 14, using a REAL registered PRM-tier bot
    (deepthought.py) loaded via the real file-based loader -- exactly the test
    shape Task 9-11's synthetic-stub-player tests missed, since none of those
    stub players ever sliced ctx.bet_history.

    deepthought.py's algo() calls self._sync(ctx) unconditionally on every
    single turn (including the very first, opening turn), and _sync ->
    _update_bluff_obs does `history[self._bluff_history_seen :]` -- an
    open-ended slice on ctx.bet_history. Before the readmodel.py fix, that
    raised TypeError on every isolated call, so DeepThought hit the engine's
    `except Exception: loser = player_idx; stats.record_penalty(...)` path on
    every single turn -- 0 wins across any number of games (confirmed via a
    real `just simulate-season` run, see .superpowers/sdd/progress.md).
    """
    shutil.copy(_DEEPTHOUGHT_SRC, tmp_path / "deepthought.py")
    (tmp_path / "simplecaller.py").write_text(_OPPONENT_SRC)

    players = import_player_classes_from_dir(str(tmp_path))
    assert {type(p).__name__ for p in players} == {"DeepThought", "SimpleCaller"}

    result = run_series(
        players,
        n_games=3,
        capture_outcomes=True,
        isolated=True,
        worker_timeout_s=5.0,
    )

    # The bug fires on literally every algo() call (including the opening
    # bid), so under the bug DeepThought is penalized every single turn it
    # ever takes and never wins a round. With the fix, it should never be
    # penalized at all across a normal 3-game series.
    assert result.stats.penalty_count.get("Deep Thought", 0) == 0
    # Sanity: the series actually completed 3 games' worth of normal play,
    # not 3 immediate forfeits.
    assert sum(result.wins.values()) == 3
    assert len(result.outcomes) > 0
