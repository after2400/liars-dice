"""Self-contained tests for the template player.

Copy this alongside your own player (e.g. `tests/test_fred.py`) and adapt it.
These tests reference only the example player, so they never bit-rot against
real players, yet they run as part of the suite to prove the template still
works against the live game engine.
"""

from examples.players.example import Example
from game.components.bets import Bet, bet_validator

NO_HISTORY: list[dict] = []
NO_OUTCOMES: list[dict] = []


def _prior(quantity: int, face: int) -> Bet:
    """A prior bet from some other player."""
    return Bet(quantity, face, "prior")


def test_opens_with_most_held_face():
    # Holds three 4s plus a wild 1 -> opens 4x4 (3 fours + 1 wild).
    bet = Example().algo([4, 4, 4, 1, 2], None, 30, NO_HISTORY, NO_OUTCOMES)
    assert bet is not None
    assert (bet.quantity, bet.face) == (4, 4)
    assert bet.player == "Example"


def test_open_bid_is_at_least_one():
    # No wilds, one of each non-1 face -> still a legal quantity (>= 1).
    bet = Example().algo([2, 3, 4, 5, 6], None, 30, NO_HISTORY, NO_OUTCOMES)
    assert bet is not None
    assert bet.quantity >= 1


def test_calls_liar_when_prior_exceeds_a_third():
    # 12 dice in play, prior claims 5 -> 5 > 12/3 -> call liar.
    result = Example().algo([1, 2, 3, 4, 5], _prior(5, 4), 12, NO_HISTORY, NO_OUTCOMES)
    assert result is None


def test_raises_when_prior_is_modest():
    # 30 dice, prior claims only 2 -> raise to the same face, one more die.
    result = Example().algo([1, 2, 3, 4, 5], _prior(2, 4), 30, NO_HISTORY, NO_OUTCOMES)
    assert result is not None
    assert (result.quantity, result.face) == (3, 4)


def test_raise_is_a_legal_bet():
    prior = _prior(2, 4)
    result = Example().algo([1, 2, 3, 4, 5], prior, 30, NO_HISTORY, NO_OUTCOMES)
    assert result is not None
    assert bet_validator(prior, result) is True
