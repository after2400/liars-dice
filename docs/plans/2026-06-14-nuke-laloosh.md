# Nuke LaLoosh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Nuke LaLoosh, a Liar's Dice player who opens on 1s ~75% of the time (turning wilds off for the round), uses Diego's binomial probability engine for liar-calling, and raises aggressively when backed.

**Architecture:** Single file `players/nuke.py` with two tunable constants (`CALL_THRESHOLD`, `RAISE_WHEN_BACKED`). We implement once, run simulations across three parameter combinations, and lock in the best performer. No leaderboard edit needed — the PR merge triggers auto-registration.

**Tech Stack:** Python 3.14, `math.comb` for binomial probability, `random.random` for pitch selection, `uv run pytest` for tests, `just simulate-season` for empirical tuning.

---

### Task 1: Write failing tests for Nuke

**Files:**

- Create: `tests/test_nuke.py`
- Modify: `tests/test_validate_player.py` (add one line: real-player validation smoke test)

- [ ] **Step 1: Write `tests/test_nuke.py`**

```python
import random
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


def test_player_name(nuke):
    """Player name attribute is set correctly."""
    assert nuke.name == "Nuke LaLoosh"
```

- [ ] **Step 2: Add real-player smoke test to `tests/test_validate_player.py`**

Append this function at the end of `tests/test_validate_player.py`:

```python
def test_real_player_nuke():
    """Real player nuke.py passes validation."""
    result = _run(REPO_ROOT / "players" / "nuke.py")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK" in result.stdout
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
uv run pytest tests/test_nuke.py tests/test_validate_player.py::test_real_player_nuke -v
```

Expected: All tests in `test_nuke.py` FAIL with `ModuleNotFoundError: No module named 'players.nuke'`. The validate test also fails. This confirms the tests are wired correctly.

---

### Task 2: Implement `players/nuke.py`

**Files:**

- Create: `players/nuke.py`

- [ ] **Step 1: Create `players/nuke.py`**

Start with **Variant A** constants (we tune in Task 3):

```python
import random
from math import comb

from game.components.bets import Bet


class Nuke:
    """
    "Nuke LaLoosh" — raw talent, zero discipline. Opens on 1s ~75% of the time
    (his fastball), turning wilds off for the round and disrupting everyone's
    expected counts. Occasionally throws a changeup (best non-1 face, Diego-style).

    Liar-calling uses Diego's exact binomial but with CALL_THRESHOLD tuned for
    Nuke's personality. Raises by RAISE_WHEN_BACKED when he has backing.
    """

    name = "Nuke LaLoosh"

    FASTBALL_PROB = 0.75   # probability of opening on 1s
    CALL_THRESHOLD = 0.20  # call liar when P(bet holds) < this
    RAISE_WHEN_BACKED = 1  # quantity raise when holding the prior face

    def _prob_bet_holds(self, hand: list[int], face: int, quantity: int, total_dice: int) -> float:
        own = hand.count(face) + (hand.count(1) if face != 1 else 0)
        unseen = total_dice - len(hand)
        p = 1 / 6 if face == 1 else 2 / 6
        need = quantity - own
        if need <= 0:
            return 1.0
        if need > unseen:
            return 0.0
        return sum(
            comb(unseen, k) * (p**k) * ((1 - p) ** (unseen - k))
            for k in range(need, unseen + 1)
        )

    def algo(
        self,
        hand: list[int],
        prior_bet: Bet | None,
        total_dice: int,
        bet_history: list[dict],
        outcomes: list[dict],
    ) -> Bet | None:
        if prior_bet is None:
            if random.random() < self.FASTBALL_PROB:
                # Fastball: open on 1s, turning wilds off for the round
                own_1s = hand.count(1)
                unseen = total_dice - len(hand)
                quantity = max(own_1s + 1, round(own_1s + unseen * (1 / 6) * 0.7))
                return Bet(quantity, 1, self.name)
            # Changeup: best non-1 face, Diego's opening formula
            best_face = max(range(2, 7), key=lambda f: hand.count(f) + hand.count(1))
            own = hand.count(best_face) + hand.count(1)
            unseen = total_dice - len(hand)
            quantity = max(1, round(own + unseen * (2 / 6) * 0.7))
            return Bet(quantity, best_face, self.name)

        if self._prob_bet_holds(hand, prior_bet.face, prior_bet.quantity, total_dice) < self.CALL_THRESHOLD:
            return None

        own_on_face = hand.count(prior_bet.face) + (hand.count(1) if prior_bet.face != 1 else 0)
        if own_on_face > 0:
            return Bet(prior_bet.quantity + self.RAISE_WHEN_BACKED, prior_bet.face, self.name)

        for face in range(prior_bet.face + 1, 7):
            if hand.count(face) + hand.count(1) > 0:
                return Bet(prior_bet.quantity, face, self.name)

        return Bet(prior_bet.quantity + 1, prior_bet.face, self.name)
```

- [ ] **Step 2: Run tests to verify they pass**

```bash
uv run pytest tests/test_nuke.py tests/test_validate_player.py::test_real_player_nuke -v
```

Expected: All 11 tests PASS.

- [ ] **Step 3: Run the full suite to check for regressions**

```bash
uv run pytest -v
```

Expected: 149 passed (138 existing + 11 new), 0 failures.

- [ ] **Step 4: Commit**

```bash
git add players/nuke.py tests/test_nuke.py tests/test_validate_player.py
git commit -m "feat(players): add Nuke LaLoosh"
```

---

### Task 3: Simulate all three variants and pick the winner

The three variants differ only in `CALL_THRESHOLD` and `RAISE_WHEN_BACKED`. Run `just simulate-season` with each, note the L1 win rate, and pick the variant that lands in the **CH 20-30%** target range (or closest to it).

| Variant | `CALL_THRESHOLD` | `RAISE_WHEN_BACKED` |
| ------- | ---------------- | ------------------- |
| A       | 0.20             | 1                   |
| B       | 0.30             | 2                   |
| C       | 0.20             | 2                   |

- [ ] **Step 1: Run Variant A (already set in nuke.py)**

`CALL_THRESHOLD = 0.20`, `RAISE_WHEN_BACKED = 1` — these are already the defaults from Task 2.

```bash
just simulate-season
```

Record Nuke's L1 win rate from the output. \_(Write it here: _\_\_%)_

- [ ] **Step 2: Switch to Variant B and simulate**

Edit `players/nuke.py` constants:

```python
CALL_THRESHOLD = 0.30
RAISE_WHEN_BACKED = 2
```

```bash
just simulate-season
```

Record Nuke's L1 win rate. \_(Write it here: _\_\_%)_

- [ ] **Step 3: Switch to Variant C and simulate**

Edit `players/nuke.py` constants:

```python
CALL_THRESHOLD = 0.20
RAISE_WHEN_BACKED = 2
```

```bash
just simulate-season
```

Record Nuke's L1 win rate. \_(Write it here: _\_\_%)_

- [ ] **Step 4: Set constants to the winning variant**

Pick the variant with a win rate closest to 25-35% in L1 (strong enough to earn promotion to CH). Update the constants in `players/nuke.py` accordingly.

- [ ] **Step 5: Commit the tuned constants**

```bash
git add players/nuke.py
git commit -m "chore(players): tune Nuke LaLoosh variant constants"
```
