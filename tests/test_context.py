from types import MappingProxyType

import pytest

from game.components.bets import Bet
from game.components.context import GameContext, _ReadOnlySequence


def _ros(*dicts):
    return _ReadOnlySequence(list(dicts))


def _ctx(**overrides):
    defaults = dict(
        hand=[1, 2, 3],
        prior_bet=None,
        total_dice=15,
        bet_history=_ros({"game": 1, "round": 1, "player": "Alice"}),
        outcomes=_ros({"game": 1, "round": 1, "bet_held": True}),
        stats=None,
        tier="PRM",
        round_players=["Alice", "Bob"],
    )
    return GameContext(**{**defaults, **overrides})


# ---------------------------------------------------------------------------
# _ReadOnlySequence
# ---------------------------------------------------------------------------


def test_ros_len_and_getitem():
    ros = _ros({"a": 1}, {"b": 2})
    assert len(ros) == 2
    assert ros[0]["a"] == 1


def test_ros_iter():
    ros = _ros({"x": 10})
    items = list(ros)
    assert items[0]["x"] == 10


def test_ros_entry_is_mapping_proxy():
    ros = _ros({"k": "v"})
    assert isinstance(ros[0], MappingProxyType)


def test_ros_entry_mutation_blocked():
    ros = _ros({"k": "v"})
    with pytest.raises(TypeError):
        ros[0]["k"] = "evil"


def test_ros_no_append():
    ros = _ReadOnlySequence([])
    assert not hasattr(ros, "append")


def test_ros_no_setattr():
    ros = _ReadOnlySequence([])
    with pytest.raises(AttributeError):
        ros._data = []  # type: ignore[misc]


def test_ros_reflects_live_list():
    data: list = []
    ros = _ReadOnlySequence(data)
    assert len(ros) == 0
    data.append({"new": True})
    assert len(ros) == 1


# ---------------------------------------------------------------------------
# GameContext — hand
# ---------------------------------------------------------------------------


def test_hand_returns_list():
    assert isinstance(_ctx().hand, list)


def test_hand_returns_correct_values():
    assert _ctx(hand=[3, 3, 1]).hand == [3, 3, 1]


def test_hand_mutation_does_not_affect_ctx():
    ctx = _ctx(hand=[1, 2, 3])
    ctx.hand.append(99)
    assert ctx.hand == [1, 2, 3]


def test_hand_is_not_settable():
    with pytest.raises(AttributeError):
        _ctx().hand = [1, 2, 3]


# ---------------------------------------------------------------------------
# GameContext — prior_bet
# ---------------------------------------------------------------------------


def test_prior_bet_none():
    assert _ctx(prior_bet=None).prior_bet is None


def test_prior_bet_returned():
    bet = Bet(2, 3, "Alice")
    assert _ctx(prior_bet=bet).prior_bet is bet


def test_prior_bet_is_not_settable():
    with pytest.raises(AttributeError):
        _ctx().prior_bet = None


# ---------------------------------------------------------------------------
# GameContext — total_dice
# ---------------------------------------------------------------------------


def test_total_dice_returned():
    assert _ctx(total_dice=12).total_dice == 12


def test_total_dice_is_not_settable():
    with pytest.raises(AttributeError):
        _ctx().total_dice = 99


# ---------------------------------------------------------------------------
# GameContext — bet_history
# ---------------------------------------------------------------------------


def test_bet_history_returns_read_only_sequence():
    assert isinstance(_ctx().bet_history, _ReadOnlySequence)


def test_bet_history_entries_are_readonly():
    ctx = _ctx()
    with pytest.raises(TypeError):
        ctx.bet_history[0]["player"] = "hacked"


def test_bet_history_has_no_append():
    assert not hasattr(_ctx().bet_history, "append")


def test_bet_history_is_not_settable():
    with pytest.raises(AttributeError):
        _ctx().bet_history = _ReadOnlySequence([])


# ---------------------------------------------------------------------------
# GameContext — outcomes
# ---------------------------------------------------------------------------


def test_outcomes_returns_read_only_sequence():
    assert isinstance(_ctx().outcomes, _ReadOnlySequence)


def test_outcomes_entries_are_readonly():
    ctx = _ctx()
    with pytest.raises(TypeError):
        ctx.outcomes[0]["bet_held"] = False


def test_outcomes_has_no_append():
    assert not hasattr(_ctx().outcomes, "append")


def test_outcomes_is_not_settable():
    with pytest.raises(AttributeError):
        _ctx().outcomes = _ReadOnlySequence([])


# ---------------------------------------------------------------------------
# GameContext — stats
# ---------------------------------------------------------------------------


def test_stats_none_becomes_gamestats():
    from game.components.stats import GameStats

    assert isinstance(_ctx(stats=None).stats, GameStats)


def test_stats_is_not_settable():
    with pytest.raises(AttributeError):
        _ctx().stats = None


# ---------------------------------------------------------------------------
# GameContext — tier
# ---------------------------------------------------------------------------


def test_tier_returned():
    assert _ctx(tier="CH").tier == "CH"


def test_tier_none_allowed():
    assert _ctx(tier=None).tier is None


def test_tier_is_not_settable():
    with pytest.raises(AttributeError):
        _ctx().tier = "PRM"


# ---------------------------------------------------------------------------
# GameContext — round_players
# ---------------------------------------------------------------------------


def test_round_players_returns_list():
    assert isinstance(_ctx().round_players, list)


def test_round_players_values():
    assert _ctx(round_players=["X", "Y"]).round_players == ["X", "Y"]


def test_round_players_mutation_isolated():
    ctx = _ctx(round_players=["Alice", "Bob"])
    ctx.round_players.append("Eve")
    assert ctx.round_players == ["Alice", "Bob"]


def test_round_players_is_not_settable():
    with pytest.raises(AttributeError):
        _ctx().round_players = []


# ---------------------------------------------------------------------------
# GameContext — repr
# ---------------------------------------------------------------------------


def test_repr_contains_total_dice():
    assert "15" in repr(_ctx(total_dice=15))
