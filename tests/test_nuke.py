import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from game.components.bets import Bet
from players.nuke import Nuke

REPO_ROOT = Path(__file__).parent.parent


@pytest.fixture
def nuke():
    return Nuke()


# Two-player endgame outcomes (starting pool=2, current=2 → threshold=2, eligible)
_ENDGAME_2P = [{"hands": {"PlayerA": [1, 2, 3, 4, 5], "Nuke LaLoosh": [1, 3, 4, 5, 6]}}]


# --- Opening bid ---


def test_fastball_opens_on_ones(nuke):
    """When random() < 0.50 and in 2-player endgame with 1s held, Nuke opens on 1s."""
    hand = [1, 3, 4, 5, 6]
    with patch("players.nuke.random.random", return_value=0.3):
        bet = nuke.algo(hand, None, 10, [], _ENDGAME_2P)
    assert bet.face == 1
    assert bet.player == "Nuke LaLoosh"


def test_fastball_quantity_formula_formula_term_wins(nuke):
    """Opening 1s quantity: max(own+1, round(own + unseen*(1/6)*0.7)).
    With one 1 and 5 unseen (total=10): max(2, round(1+0.58)) = max(2, 2) = 2."""
    hand = [1, 3, 4, 5, 6]  # own_1s=1, unseen=5 at total_dice=10
    with patch("players.nuke.random.random", return_value=0.0):
        bet = nuke.algo(hand, None, 10, [], _ENDGAME_2P)
    assert bet.quantity == 2


def test_fastball_quantity_formula_plus_one_wins_in_endgame(nuke):
    """own+1 beats scaled formula when Nuke holds many 1s vs few unseen.
    Three 1s, 2 unseen (total=7): max(4, round(3+0.23)) = max(4, 3) = 4."""
    hand = [1, 1, 1, 2, 3]  # own_1s=3, total_dice=7, unseen=2
    outcomes = [{"hands": {"PlayerA": [2, 3], "Nuke LaLoosh": [1, 1, 1, 2, 3]}}]
    with patch("players.nuke.random.random", return_value=0.0):
        bet = nuke.algo(hand, None, 7, [], outcomes)
    assert bet.quantity == 4


def test_fastball_not_thrown_outside_endgame(nuke):
    """Fastball suppressed when above threshold players remain (6-player start → threshold=3, current=6)."""
    hand = [1, 3, 4, 5, 6]
    outcomes = [{"hands": {f"P{i}": [1, 2, 3, 4, 5] for i in range(6)}}]
    with patch("players.nuke.random.random", return_value=0.1):
        bet = nuke.algo(hand, None, 30, [], outcomes)
    assert bet.face != 1


def test_fastball_thrown_at_3_players_in_large_game(nuke):
    """In a 6-player-start game, fastball fires when down to 3 (threshold=3)."""
    hand = [1, 3, 4, 5, 6]
    outcomes = [
        {"hands": {f"P{i}": [1, 2, 3, 4, 5] for i in range(6)}},
        {"hands": {"P0": [1, 2, 3], "P1": [4, 5], "Nuke LaLoosh": [1, 3, 4, 5, 6]}},
    ]
    with patch("players.nuke.random.random", return_value=0.1):
        bet = nuke.algo(hand, None, 10, [], outcomes)
    assert bet.face == 1


def test_fastball_falls_through_to_changeup_when_no_ones(nuke):
    """Fastball eligible by count but hand has no 1s — falls through to changeup."""
    hand = [3, 3, 4, 5, 6]  # no 1s
    with patch("players.nuke.random.random", return_value=0.1):
        bet = nuke.algo(hand, None, 10, [], _ENDGAME_2P)
    assert bet.face != 1


def test_changeup_opens_on_best_non_one_face(nuke):
    """When random() >= 0.50, Nuke throws a changeup: best non-1 face."""
    hand = [3, 3, 3, 4, 5]  # best face is 3
    with patch("players.nuke.random.random", return_value=0.8):
        bet = nuke.algo(hand, None, 20, [], _ENDGAME_2P)
    assert bet.face == 3


def test_changeup_quantity_uses_opening_formula(nuke):
    """Changeup quantity: max(1, round(own + unseen*(2/6)*0.82)).
    Three 3s, unseen=19 (total=24): max(1, round(3+5.19)) = 8."""
    hand = [3, 3, 3, 4, 5]  # own=3, unseen=19 at total_dice=24
    with patch("players.nuke.random.random", return_value=0.8):
        bet = nuke.algo(hand, None, 24, [], [])
    assert bet.quantity == 8


# --- 1s follow-up (backed only) ---


def test_raises_on_ones_when_holding_them(nuke):
    """Raises on 1s when Nuke personally holds them (backed).
    Two 1s held, prior=Bet(3,1): own_1s=2, backed → raise.
    _raise_amount: P(5 ones, 2 own, 15 unseen) = P(X>=3, X~Binom(15,1/6)) ≈ 0.47 >= 0.40 → +2."""
    hand = [1, 1, 2, 3, 4]
    prior_bet = Bet(3, 1, "someone")
    result = nuke.algo(hand, prior_bet, 20, [], [])
    assert result is not None
    assert result.face == 1
    assert result.quantity == 5  # prior(3) + 2


def test_stays_on_ones_without_holding_when_bet_is_credible(nuke):
    """Stays on 1s even without holding any, while P(current 1s bet) >= FASTBALL_HOLD_THRESHOLD.
    No 1s in hand; prior=Bet(2,1): P(X>=2, Binom(15,1/6)) ≈ 0.74 >= 0.40 → keeps raising on 1s."""
    hand = [3, 3, 4, 5, 6]
    prior_bet = Bet(2, 1, "someone")
    result = nuke.algo(hand, prior_bet, 20, [], [])
    assert result is not None
    assert result.face == 1


def test_leaves_ones_when_not_holding_them(nuke):
    """Shifts off 1s when Nuke holds none and the 1s bid is no longer credible.
    No 1s in hand; prior=Bet(4,1): P(X>=4, Binom(15,1/6)) ≈ 0.25 < FASTBALL_HOLD_THRESHOLD
    → threshold not met → shifts to best held face."""
    hand = [3, 3, 4, 5, 6]
    prior_bet = Bet(4, 1, "someone")
    result = nuke.algo(hand, prior_bet, 20, [], [])
    assert result is not None
    assert result.face != 1


# --- Probability-weighted raise ---


def test_raises_by_two_when_probability_supports_it(nuke):
    """Goes +2 when P(quantity+2, face) >= RAISE_TWO_THRESHOLD.
    Backed on 3s (2 held), prior=3: P(5 threes) = P(X>=3, X~Binom(15,1/3)) ≈ 0.94 >= 0.40."""
    hand = [3, 3, 4, 5, 6]  # two 3s, unseen=15
    prior_bet = Bet(3, 3, "someone")
    result = nuke.algo(hand, prior_bet, 20, [], [])
    assert result is not None
    assert result.face == 3
    assert result.quantity == 5  # prior(3) + 2


def test_raises_by_one_when_plus_two_is_risky(nuke):
    """Goes +1 when P(quantity+2) < RAISE_TWO_THRESHOLD but own bid is still defensible.
    Backed on 3s (4 held), prior=8: P(10 threes) = P(X>=6, X~Binom(15,1/3)) ≈ 0.40 < threshold → +1.
    P(9 threes) = P(X>=5) ≈ 0.61 >= _own_bid_threshold(20)=0.40 → make the bid."""
    hand = [3, 3, 3, 3, 4]  # four 3s, unseen=15
    prior_bet = Bet(8, 3, "someone")
    result = nuke.algo(hand, prior_bet, 20, [], [])
    assert result is not None
    assert result.face == 3
    assert result.quantity == 9  # prior(8) + 1


# --- Liar calling (based on own counter-bid, not prior bet) ---


def test_calls_liar_when_prior_bet_is_implausible(nuke):
    """Calls liar immediately when P(prior bet) < BLUFF_CALL_THRESHOLD, regardless of own bid.
    Prior=Bet(18,3): P(X>=18, Binom(15,1/3)) ≈ 0.0 < 0.15 → call liar."""
    hand = [3, 3, 4, 5, 6]
    prior_bet = Bet(18, 3, "someone")
    result = nuke.algo(hand, prior_bet, 20, [], [])
    assert result is None


def test_calls_liar_when_own_bid_is_indefensible(nuke):
    """Returns None when Nuke's best counter-bid is indefensible (P < _own_bid_threshold).
    Prior is 18 threes; best shift is to 4s. P(18 fours, 1 held, 15 unseen) = 0.0."""
    hand = [2, 4, 5, 6, 6]  # no 3s, no 1s; holds one 4
    prior_bet = Bet(18, 3, "someone")
    result = nuke.algo(hand, prior_bet, 20, [], [])
    assert result is None


def test_does_not_call_liar_when_own_bid_is_defensible(nuke):
    """Does not call liar when Nuke's counter-bid has reasonable probability."""
    hand = [3, 3, 4, 5, 6]  # two 3s
    prior_bet = Bet(3, 3, "someone")
    result = nuke.algo(hand, prior_bet, 20, [], [])
    assert result is not None


# --- Face-shifting and last resort ---


def test_shifts_to_higher_held_face_when_not_backed(nuke):
    """When not holding the prior face, shifts to lowest higher face held.
    No 3s or 1s; holds 5 and 6 → shifts to 5 at same quantity."""
    hand = [5, 5, 6, 6, 6]
    prior_bet = Bet(2, 3, "someone")
    result = nuke.algo(hand, prior_bet, 20, [], [])
    assert result is not None
    assert result.face == 5
    assert result.quantity == 2


def test_last_resort_raises_quantity_on_same_face(nuke):
    """When no higher face is held and not backed, raises quantity on same face.
    Only holds 2s, prior face 3: last resort. P(4 threes, 0 held, 15 unseen) ≈ 0.80 >= 0.40 → +2."""
    hand = [2, 2, 2, 2, 2]  # only 2s, prior face is 3
    prior_bet = Bet(2, 3, "someone")
    result = nuke.algo(hand, prior_bet, 20, [], [])
    assert result is not None
    assert result.face == 3
    assert result.quantity == 4  # prior(2) + 2


def test_last_resort_from_face_six(nuke):
    """Last-resort fires when prior face is 6 (no higher face exists).
    P(5 sixes, 0 held, 15 unseen) = P(X>=5, X~Binom(15,1/3)) ≈ 0.61 >= 0.40 → +2."""
    hand = [2, 2, 3, 3, 4]  # no 6s, no 1s
    prior_bet = Bet(3, 6, "someone")
    result = nuke.algo(hand, prior_bet, 20, [], [])
    assert result is not None
    assert result.face == 6
    assert result.quantity == 5  # prior(3) + 2


def test_player_name(nuke):
    """Player name attribute is set correctly."""
    assert nuke.name == "Nuke LaLoosh"


def test_tier_l1_opens_more_aggressively_than_prm(nuke):
    """In L1 Nuke uses 0.85; in PRM 0.78 — producing a measurably higher opening bid.
    hand=[3,2,4,5,6] (5 dice, no 1s), total_dice=28 → unseen=23, best_face=2, own=1:
      L1  (0.85): max(1, round(1+23*(2/6)*0.85)) = max(1, round(7.52)) = 8
      PRM (0.78): max(1, round(1+23*(2/6)*0.78)) = max(1, round(6.98)) = 7"""
    hand = [3, 2, 4, 5, 6]  # all different, no 1s; best_face=2 (first with max count), own=1
    with patch("players.nuke.random.random", return_value=0.8):  # no fastball
        bet_l1 = nuke.algo(hand, None, 28, [], [], tier="L1")
        bet_prm = nuke.algo(hand, None, 28, [], [], tier="PRM")
    assert bet_l1.quantity == 8
    assert bet_prm.quantity == 7


def test_tier_ch_uses_calibrated_opening_multiplier(nuke):
    """In CH, Nuke uses the 0.82 multiplier.
    hand=[3,2,4,5,6], total_dice=28, unseen=23, best_face=2, own=1:
      CH (0.82): max(1, round(1+23*(2/6)*0.82)) = max(1, round(7.29)) = 7."""
    hand = [3, 2, 4, 5, 6]
    with patch("players.nuke.random.random", return_value=0.8):
        bet = nuke.algo(hand, None, 28, [], [], tier="CH")
    assert bet.quantity == 7


def test_tier_none_uses_default_multiplier(nuke):
    """With tier=None (tournament), uses the same 0.82 multiplier as CH.
    hand=[3,2,4,5,6], total_dice=28: max(1, round(7.29)) = 7."""
    hand = [3, 2, 4, 5, 6]
    with patch("players.nuke.random.random", return_value=0.8):
        bet = nuke.algo(hand, None, 28, [], [], tier=None)
    assert bet.quantity == 7


def test_nuke_passes_validation():
    """nuke.py passes the registration validator (exits 0)."""
    result = subprocess.run(
        ["uv", "run", "python", "-m", "game.validate", str(REPO_ROOT / "players" / "nuke.py")],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK" in result.stdout
