"""Tests for the Topper and Pyro (Liar², Pants on Fire) players.

Both step bids up one notch in (quantity, face) order over faces 2-6:
bump the face by 1, and once the face is 6, increment quantity and reset
face to 2. They differ only in when they call liar:

  * Topper calls liar when the step would need more dice than are in play.
  * Pyro calls liar when the step's quantity would exceed 1/3 of the dice.

Both open (no prior bet) with a break-even (total_dice // 3) quantity, clamped
to >= 1: Topper at the ceiling (sixes), Pyro one rung below (fives).
"""

from game.components.bets import Bet, bet_validator
from players.pyro import Pyro
from players.topper import Topper

NO_HISTORY: list = []
NO_OUTCOMES: list = []


def _bet(quantity, face):
    return Bet(quantity, face, "Prior")


# ---------------------------------------------------------------------------
# Opening bids (shared rule)
# ---------------------------------------------------------------------------


def test_topper_opens_with_third_of_dice_in_sixes():
    bet = Topper().algo([], None, 12, NO_HISTORY, NO_OUTCOMES)
    assert (bet.quantity, bet.face) == (4, 6)


def test_topper_open_quantity_truncates_toward_third():
    # 13 and 14 dice both floor to quantity 4; only 15 reaches quantity 5.
    assert Topper().algo([], None, 13, NO_HISTORY, NO_OUTCOMES).quantity == 4
    assert Topper().algo([], None, 14, NO_HISTORY, NO_OUTCOMES).quantity == 4
    assert Topper().algo([], None, 15, NO_HISTORY, NO_OUTCOMES).quantity == 5


def test_open_quantity_clamped_to_one_for_few_dice():
    # 2 dice -> //3 == 0, clamp up to a legal quantity of 1.
    bet = Topper().algo([], None, 2, NO_HISTORY, NO_OUTCOMES)
    assert (bet.quantity, bet.face) == (1, 6)


def test_open_quantity_scales_with_many_dice():
    # 21 dice -> //3 == 7; quantity is uncapped (face is the fixed ceiling).
    bet = Topper().algo([], None, 21, NO_HISTORY, NO_OUTCOMES)
    assert (bet.quantity, bet.face) == (7, 6)


def test_pyro_opens_in_fives_one_below_topper():
    bet = Pyro().algo([], None, 15, NO_HISTORY, NO_OUTCOMES)
    assert (bet.quantity, bet.face) == (5, 5)
    # Same break-even quantity as Topper, one face below his sixes.
    assert bet.quantity == Topper().algo([], None, 15, NO_HISTORY, NO_OUTCOMES).quantity
    assert bet.face == Topper().algo([], None, 15, NO_HISTORY, NO_OUTCOMES).face - 1


# ---------------------------------------------------------------------------
# Topper stepping / liar
# ---------------------------------------------------------------------------


def test_topper_bumps_face():
    bet = Topper().algo([], _bet(3, 4), 12, NO_HISTORY, NO_OUTCOMES)
    assert (bet.quantity, bet.face) == (3, 5)
    assert bet_validator(_bet(3, 4), bet)
    assert bet.player == "Topper"


def test_topper_wraps_face_six_to_next_quantity():
    bet = Topper().algo([], _bet(4, 6), 12, NO_HISTORY, NO_OUTCOMES)
    assert (bet.quantity, bet.face) == (5, 2)
    assert bet_validator(_bet(4, 6), bet)


def test_topper_calls_liar_when_step_exceeds_available_dice():
    # Prior is 12x6 with 12 dice: the only step (13x2) needs more dice than exist.
    assert Topper().algo([], _bet(12, 6), 12, NO_HISTORY, NO_OUTCOMES) is None


def test_topper_does_not_call_liar_while_dice_remain():
    # Wrapping 4x6 -> 5x2 with 12 dice is still within reach.
    assert Topper().algo([], _bet(4, 6), 12, NO_HISTORY, NO_OUTCOMES) is not None


# ---------------------------------------------------------------------------
# Pyro stepping / liar (the 1/3 threshold)
# ---------------------------------------------------------------------------


def test_pyro_acts_as_topper_below_threshold():
    bet = Pyro().algo([], _bet(3, 4), 12, NO_HISTORY, NO_OUTCOMES)
    assert (bet.quantity, bet.face) == (3, 5)


def test_pyro_calls_liar_when_step_quantity_exceeds_third():
    # The canonical case: 4x6 with 12 dice -> step is 5x2, and 5 > 12/3 -> liar.
    assert Pyro().algo([], _bet(4, 6), 12, NO_HISTORY, NO_OUTCOMES) is None


def test_pyro_bids_at_exactly_the_threshold():
    # 4x5 -> 4x6 with 12 dice: quantity 4 is not > 12/3, so she bids.
    bet = Pyro().algo([], _bet(4, 5), 12, NO_HISTORY, NO_OUTCOMES)
    assert (bet.quantity, bet.face) == (4, 6)


def test_pyro_threshold_scales_with_dice():
    # 15 dice -> threshold 5. 4x6 -> 5x2 (quantity 5 not > 5) bids;
    # 5x6 -> 6x2 (quantity 6 > 5) calls liar.
    assert Pyro().algo([], _bet(4, 6), 15, NO_HISTORY, NO_OUTCOMES) is not None
    assert Pyro().algo([], _bet(5, 6), 15, NO_HISTORY, NO_OUTCOMES) is None
