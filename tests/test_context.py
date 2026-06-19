from types import MappingProxyType

import pytest

from game.components.bets import Bet
from game.components.context import GameContext


def _ctx(**overrides):
    defaults = dict(
        hand=[1, 2, 3],
        prior_bet=None,
        total_dice=15,
        bet_history=[MappingProxyType({"game": 1, "round": 1, "player": "Alice"})],
        outcomes=[MappingProxyType({"game": 1, "round": 1, "bet_held": True})],
        stats=None,
        tier="PRM",
        round_players=["Alice", "Bob"],
    )
    return GameContext(**{**defaults, **overrides})


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


def test_prior_bet_none():
    assert _ctx(prior_bet=None).prior_bet is None


def test_prior_bet_returned():
    bet = Bet(2, 3, "Alice")
    assert _ctx(prior_bet=bet).prior_bet is bet


def test_prior_bet_is_not_settable():
    with pytest.raises(AttributeError):
        _ctx().prior_bet = None


def test_total_dice_returned():
    assert _ctx(total_dice=12).total_dice == 12


def test_total_dice_is_not_settable():
    with pytest.raises(AttributeError):
        _ctx().total_dice = 99


def test_bet_history_returns_list():
    assert isinstance(_ctx().bet_history, list)


def test_bet_history_entries_are_readonly():
    ctx = _ctx()
    with pytest.raises(TypeError):
        ctx.bet_history[0]["player"] = "hacked"


def test_bet_history_list_mutation_isolated_between_instances():
    entries = [MappingProxyType({"game": 1})]
    ctx1 = _ctx(bet_history=entries)
    ctx2 = _ctx(bet_history=entries)
    ctx1.bet_history.append("injected")
    assert len(ctx2.bet_history) == 1


def test_bet_history_is_not_settable():
    with pytest.raises(AttributeError):
        _ctx().bet_history = []


def test_outcomes_entries_are_readonly():
    ctx = _ctx()
    with pytest.raises(TypeError):
        ctx.outcomes[0]["bet_held"] = False


def test_outcomes_is_not_settable():
    with pytest.raises(AttributeError):
        _ctx().outcomes = []


def test_stats_none_becomes_gamestats():
    from game.components.stats import GameStats

    assert isinstance(_ctx(stats=None).stats, GameStats)


def test_stats_is_not_settable():
    with pytest.raises(AttributeError):
        _ctx().stats = None


def test_tier_returned():
    assert _ctx(tier="CH").tier == "CH"


def test_tier_none_allowed():
    assert _ctx(tier=None).tier is None


def test_tier_is_not_settable():
    with pytest.raises(AttributeError):
        _ctx().tier = "PRM"


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


def test_repr_contains_total_dice():
    assert "15" in repr(_ctx(total_dice=15))
