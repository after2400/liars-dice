"""Tests for GameContext v2: _ReadOnlySequence, GameContext, orchestrator dispatch, validate."""

import subprocess
from pathlib import Path

import pytest

from game.components.context import GameContext, _ReadOnlySequence
from game.components.script import game_orchestrator
from game.components.stats import GameStats

REPO_ROOT = Path(__file__).parent.parent


# ---------------------------------------------------------------------------
# _ReadOnlySequence
# ---------------------------------------------------------------------------


def test_read_only_sequence_len_and_getitem():
    data = [{"a": 1}, {"b": 2}]
    ros = _ReadOnlySequence(data)
    assert len(ros) == 2
    assert ros[0]["a"] == 1


def test_read_only_sequence_iter():
    data = [{"x": 10}]
    ros = _ReadOnlySequence(data)
    items = list(ros)
    assert items[0]["x"] == 10


def test_read_only_sequence_entry_is_mapping_proxy():
    from types import MappingProxyType

    ros = _ReadOnlySequence([{"k": "v"}])
    assert isinstance(ros[0], MappingProxyType)


def test_read_only_sequence_entry_mutation_blocked():
    ros = _ReadOnlySequence([{"k": "v"}])
    with pytest.raises(TypeError):
        ros[0]["k"] = "evil"


def test_read_only_sequence_no_append():
    ros = _ReadOnlySequence([])
    assert not hasattr(ros, "append")


def test_read_only_sequence_no_setattr():
    ros = _ReadOnlySequence([])
    with pytest.raises(AttributeError):
        ros._data = []  # type: ignore[misc]


def test_read_only_sequence_reflects_live_list():
    data: list = []
    ros = _ReadOnlySequence(data)
    assert len(ros) == 0
    data.append({"new": True})
    assert len(ros) == 1


# ---------------------------------------------------------------------------
# GameContext
# ---------------------------------------------------------------------------


def test_game_context_frozen():
    ctx = GameContext(
        hand=[1, 2],
        prior_bet=None,
        total_dice=10,
        bet_history=_ReadOnlySequence([]),
        outcomes=_ReadOnlySequence([]),
        stats=GameStats(),
        tier=None,
        round_players=[],
    )
    with pytest.raises(Exception):  # FrozenInstanceError
        ctx.hand = []  # type: ignore[misc]


# ---------------------------------------------------------------------------
# game_orchestrator: v2 player dispatch
# ---------------------------------------------------------------------------


class _V2Player:
    name = "V2Player"

    def __init__(self):
        self.received_ctx = None

    def algo(self, ctx):
        self.received_ctx = ctx
        return None  # always call liar


class _V1Player:
    name = "V1Player"

    def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):
        return None


def test_v2_player_receives_game_context():
    v2 = _V2Player()
    v1 = _V1Player()
    game_orchestrator([v2, v1], game_id=1)
    assert v2.received_ctx is not None
    assert isinstance(v2.received_ctx, GameContext)


def test_v2_bet_history_is_read_only_sequence():
    v2 = _V2Player()
    v1 = _V1Player()
    game_orchestrator([v2, v1], game_id=1)
    assert isinstance(v2.received_ctx.bet_history, _ReadOnlySequence)
    assert isinstance(v2.received_ctx.outcomes, _ReadOnlySequence)


def test_v2_stats_is_always_present():
    v2 = _V2Player()
    v1 = _V1Player()
    game_orchestrator([v2, v1], game_id=1)
    assert v2.received_ctx.stats is not None
    assert isinstance(v2.received_ctx.stats, GameStats)


def test_mixed_v1_v2_game_completes():
    v2 = _V2Player()
    v1 = _V1Player()
    winner = game_orchestrator([v2, v1], game_id=1)
    assert winner in (v2, v1)


# ---------------------------------------------------------------------------
# validate: v2 signature accepted; v1 emits deprecation warning
# ---------------------------------------------------------------------------


def _run_validate(player_path: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["uv", "run", "python", "-m", "game.validate", str(player_path)],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )


def test_validate_v2_player_ok(tmp_path):
    f = tmp_path / "fred.py"
    f.write_text("class Fred:\n    def algo(self, ctx):\n        return None\n")
    result = _run_validate(f)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK" in result.stdout
    assert "WARNING" not in result.stdout


def test_validate_v1_player_warns(tmp_path):
    f = tmp_path / "fred.py"
    f.write_text(
        "class Fred:\n"
        "    def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):\n"
        "        return None\n"
    )
    result = _run_validate(f)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "WARNING" in result.stdout
    assert "v1" in result.stdout
    assert "2026-10-05" in result.stdout
