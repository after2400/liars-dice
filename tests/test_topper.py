"""Tests for the Topper player.

Topper opens (no prior bet) with a break-even (total_dice // 3) quantity in
sixes, clamped to >= 1. Otherwise he steps the prior bid up one notch in
(quantity, face) order over faces 2-6 (bump the face by 1; once the face is 6,
increment quantity and reset face to 2), and calls liar only when that step
would need more dice than are in play.
"""

from game.components.bets import Bet, bet_validator
from players.topper import Topper

NO_HISTORY: list = []
NO_OUTCOMES: list = []


def _bet(quantity, face):
    return Bet(quantity, face, "Prior")


# --- Opening bids ---


def test_topper_opens_with_third_of_dice_in_sixes():
    bet = Topper().algo([], None, 12, NO_HISTORY, NO_OUTCOMES)
    assert (bet.quantity, bet.face) == (4, 6)


def test_topper_open_quantity_truncates_toward_third():
    # 13 and 14 dice both floor to quantity 4; only 15 reaches quantity 5.
    assert Topper().algo([], None, 13, NO_HISTORY, NO_OUTCOMES).quantity == 4
    assert Topper().algo([], None, 14, NO_HISTORY, NO_OUTCOMES).quantity == 4
    assert Topper().algo([], None, 15, NO_HISTORY, NO_OUTCOMES).quantity == 5


def test_topper_open_quantity_clamped_to_one_for_few_dice():
    # 2 dice -> //3 == 0, clamp up to a legal quantity of 1.
    bet = Topper().algo([], None, 2, NO_HISTORY, NO_OUTCOMES)
    assert (bet.quantity, bet.face) == (1, 6)


def test_topper_open_quantity_scales_with_many_dice():
    # 21 dice -> //3 == 7; quantity is uncapped (face is the fixed ceiling).
    bet = Topper().algo([], None, 21, NO_HISTORY, NO_OUTCOMES)
    assert (bet.quantity, bet.face) == (7, 6)


# --- Stepping / liar ---


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
