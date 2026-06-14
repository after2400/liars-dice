from unittest.mock import patch

import pytest

from game.components.bets import Bet
from players.nuke import Nuke


@pytest.fixture
def nuke():
    return Nuke()


# --- Opening bid ---


def test_fastball_opens_on_ones(nuke):
    """When random() < 0.75, Nuke opens on 1s (his fastball)."""
    hand = [1, 3, 4, 5, 6]
    with patch("players.nuke.random.random", return_value=0.5):
        bet = nuke.algo(hand, None, 20, [], [])
    assert bet.face == 1
    assert bet.player == "Nuke LaLoosh"


def test_fastball_quantity_formula_formula_term_wins(nuke):
    """Opening 1s quantity: max(own+1, round(own + unseen*(1/6)*0.7)).
    With one 1 and 15 unseen: max(2, round(1+1.75)) = max(2, 3) = 3."""
    hand = [1, 3, 4, 5, 6]  # own_1s=1, unseen=15 at total_dice=20
    with patch("players.nuke.random.random", return_value=0.0):
        bet = nuke.algo(hand, None, 20, [], [])
    assert bet.quantity == 3


def test_fastball_quantity_formula_plus_one_wins_in_endgame(nuke):
    """In endgame (few dice), own+1 beats the scaled formula.
    Three 1s, 4 unseen: max(4, round(3+0.47)) = max(4, 3) = 4."""
    hand = [1, 1, 1, 2, 3]  # own_1s=3, total_dice=9, unseen=4
    with patch("players.nuke.random.random", return_value=0.0):
        bet = nuke.algo(hand, None, 9, [], [])
    assert bet.quantity == 4


def test_changeup_opens_on_best_non_one_face(nuke):
    """When random() >= 0.75, Nuke throws a changeup: best non-1 face."""
    hand = [3, 3, 3, 4, 5]  # best face is 3
    with patch("players.nuke.random.random", return_value=0.8):
        bet = nuke.algo(hand, None, 20, [], [])
    assert bet.face == 3


def test_changeup_quantity_uses_diego_formula(nuke):
    """Changeup quantity: max(1, round(own + unseen*(2/6)*0.7)).
    Three 3s, unseen=19 (total=24): max(1, round(3+4.43)) = 7."""
    hand = [3, 3, 3, 4, 5]  # own=3, unseen=19 at total_dice=24
    with patch("players.nuke.random.random", return_value=0.8):
        bet = nuke.algo(hand, None, 24, [], [])
    assert bet.quantity == 7


# --- Liar calling ---


def test_calls_liar_when_probability_below_threshold(nuke):
    """Returns None when P(bet holds) < CALL_THRESHOLD."""
    hand = [2, 4, 5, 6, 6]  # no 3s, no 1s
    # Claiming 18 threes across 20 dice is essentially impossible
    prior_bet = Bet(18, 3, "someone")
    result = nuke.algo(hand, prior_bet, 20, [], [])
    assert result is None


def test_does_not_call_liar_on_reasonable_bet(nuke):
    """Does not call liar when the bet is statistically plausible."""
    hand = [3, 3, 4, 5, 6]  # two 3s
    # 3x3 with 20 dice and us holding two 3s is very plausible
    prior_bet = Bet(3, 3, "someone")
    result = nuke.algo(hand, prior_bet, 20, [], [])
    assert result is not None


# --- Raising ---


def test_raises_quantity_by_raise_when_backed(nuke):
    """When holding the prior face, raises quantity by RAISE_WHEN_BACKED."""
    hand = [3, 3, 4, 5, 6]  # two 3s → backed
    prior_bet = Bet(3, 3, "someone")
    result = nuke.algo(hand, prior_bet, 20, [], [])
    assert result is not None
    assert result.face == 3
    assert result.quantity == 3 + Nuke.RAISE_WHEN_BACKED


def test_shifts_to_higher_held_face_when_not_backed(nuke):
    """When not holding the prior face, shifts to lowest higher face we hold."""
    hand = [5, 5, 6, 6, 6]  # no 3s, holds 5 and 6
    prior_bet = Bet(2, 3, "someone")
    result = nuke.algo(hand, prior_bet, 20, [], [])
    assert result is not None
    assert result.face == 5
    assert result.quantity == 2  # same quantity, higher face


def test_last_resort_raises_quantity_blind(nuke):
    """When no higher face is held and not backed, raises quantity by 1."""
    hand = [2, 2, 2, 2, 2]  # only 2s, prior face is 3 (no backing, no higher face)
    prior_bet = Bet(2, 3, "someone")
    result = nuke.algo(hand, prior_bet, 20, [], [])
    assert result is not None
    assert result.face == 3
    assert result.quantity == 3  # +1 blind


def test_raises_quantity_by_raise_when_backed_on_ones(nuke):
    """Backed raise works correctly when the prior bet is on face 1 (no wilds counted)."""
    hand = [1, 1, 3, 4, 5]  # two 1s → backed on face 1
    prior_bet = Bet(2, 1, "someone")  # holds 2 ones, need=0 → P=1.0, well above threshold
    result = nuke.algo(hand, prior_bet, 20, [], [])
    assert result is not None
    assert result.face == 1
    assert result.quantity == 2 + Nuke.RAISE_WHEN_BACKED


def test_last_resort_from_face_six(nuke):
    """Last-resort +1 raise fires when prior face is 6 (no higher face exists)."""
    hand = [2, 2, 3, 3, 4]  # no 6s, no 1s — nothing above face 6
    prior_bet = Bet(3, 6, "someone")  # P(3+ sixes with 0 own, 15 unseen) is high
    result = nuke.algo(hand, prior_bet, 20, [], [])
    assert result is not None
    assert result.face == 6
    assert result.quantity == 4  # +1 blind


def test_player_name(nuke):
    """Player name attribute is set correctly."""
    assert nuke.name == "Nuke LaLoosh"
