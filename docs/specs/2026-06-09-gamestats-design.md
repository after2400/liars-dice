# GameStats Design Spec

**Goal:** Eliminate O(n) history scans in player algorithms by providing a pre-computed `GameStats` object as an optional 6th argument to `algo()`, then migrate all existing O(n) players to use it.

**Scope:** GameStats class + engine integration + player migrations (Eva, Zara, Sloane, Remy) + README docs. Timeout enforcement is out of scope (separate spec).

**Architecture:** A single `GameStats` instance is created at the start of `run_series()` and updated incrementally after each bet and each round outcome — O(1) per update. `game_orchestrator()` inspects each player's `algo` signature and passes `stats` as a 6th positional arg only when the player accepts it. Players that do not declare the 6th arg are unaffected.

---

## 1. GameStats Class

**File:** `game/components/stats.py` (new)

### Stats

```python
class GameStats:
    # Per-player bluff behavior (keyed by player display name)
    bluff_rate: dict[str, float]
    # (bluffs + 1) / (bluffs + holds + 2) — Laplace-smoothed fraction of bids that failed

    bluff_rate_by_face: dict[str, dict[int, float]]
    # per player, per face: Laplace-smoothed fraction of bids on that face that were bluffs

    challenge_rate: dict[str, float]
    # fraction of turns spent challenging (returning None) rather than bidding

    challenge_success_rate: dict[str, float]
    # fraction of challenges that paid off (challenger won)

    # Bid tendencies
    face_bias: dict[str, dict[int, float]]
    # per player, per face: fraction of that player's total bids placed on that face

    bid_increment: dict[str, float]
    # per player: average quantity increase per bid across all their bids

    opening_aggression: dict[str, float]
    # per player: average opening bid quantity as a fraction of total_dice at that moment

    mean_held_quantity_by_face: dict[str, dict[int, float]]
    # per player, per face: mean quantity of bids on that face that were held (bet_held=True)

    # Revealed-hand data (from outcomes["hands"])
    revealed_hand_frequency: dict[str, dict[int, float]]
    # per player, per face: average fraction of that player's dice showing that face
    # across all rounds where their hand was revealed

    rounds_with_hand: dict[str, int]
    # per player: count of rounds where their hand appeared in outcomes["hands"]

    # Current-round context (reset at the start of each new round)
    current_round_velocity: float
    # average quantity jump per bid step in the current round; 1.0 if fewer than 2 bids
```

### Internal counters (not exposed to players)

```python
    _bluff_counts: dict[str, int]        # raw bluff count per player
    _hold_counts: dict[str, int]         # raw hold count per player
    _bluff_by_face: dict[str, dict[int, int]]
    _hold_by_face: dict[str, dict[int, int]]
    _challenge_count: dict[str, int]
    _challenge_success_count: dict[str, int]
    _turn_count: dict[str, int]          # total turns (bids + challenges) per player
    _bid_count: dict[str, int]
    _face_bid_count: dict[str, dict[int, int]]
    _total_increment: dict[str, float]
    _opening_qty_sum: dict[str, float]
    _opening_count: dict[str, int]
    _held_qty_sum: dict[str, dict[int, float]]
    _held_qty_count: dict[str, dict[int, int]]
    _revealed_face_sum: dict[str, dict[int, float]]
    _revealed_dice_count: dict[str, int]
    _current_round_bets: list[int]       # quantity of each bet in the current round
    _current_round_num: int | None       # tracks when round changes
```

### Methods

```python
def update_bet(self, bet_entry: dict, is_opening_bid: bool, total_dice: int) -> None:
    """Called after each accepted bid. Updates face_bias, bid_increment, opening_aggression,
    and current_round_velocity. Does NOT update bluff/hold counts — those require outcome data."""

def update_outcome(self, outcome: dict) -> None:
    """Called after each round ends with the outcome dict. Updates bluff_rate, bluff_rate_by_face,
    challenge stats, revealed_hand_frequency, rounds_with_hand, and mean_held_quantity_by_face."""

def reset_round(self, new_round_num: int) -> None:
    """Called after update_outcome at the end of each round. Clears _current_round_bets
    so current_round_velocity reflects only the new round's bids."""
```

`is_opening_bid` is `True` when `prior_bet is None` at the time the bet is placed; `series.py` already tracks this as part of round state and passes it through.

All public attributes are recomputed from internal counters on each update — no deferred computation. Reads from player code are plain attribute/dict accesses: O(1).

---

## 2. Engine Integration

### `series.py` — `run_series()`

- Import `GameStats` from `game.components.stats`.
- Instantiate `stats = GameStats()` once before the game loop.
- After `record_bet(bet_entry)`: call `stats.update_bet(bet_entry, is_opening_bid, total_dice)`.
- After `record_outcome(outcome)`: call `stats.update_outcome(outcome)` then `stats.reset_round(next_round_num)`.

### `script.py` — `game_orchestrator()`

- At startup, for each player inspect `algo` signature:
  ```python
  import inspect
  _wants_stats = {
      p: len(inspect.signature(p.algo).parameters) >= 6
      for p in players
  }
  ```
- When calling `algo()`:
  ```python
  if _wants_stats[player]:
      move = player.algo(hand, prior_bet, total_dice, bet_history, outcomes, stats)
  else:
      move = player.algo(hand, prior_bet, total_dice, bet_history, outcomes)
  ```

No other changes to `game_orchestrator()`.

---

## 3. Player Migrations

Each migrated player adds `stats=None` as a 6th positional parameter and falls back to scanning when `stats is None` (for safety against older engines). Internal helper methods that only existed to perform the scan are removed when stats is available; the fallback path retains them.

### Eva

**Change:** `_reliability(player, outcomes)` is replaced by a bluff-rate lookup.

```python
def algo(self, hand, prior_bet, total_dice, bet_history, outcomes, stats=None):
    ...
    if stats is not None:
        bluff_rate = stats.bluff_rate.get(prior_bet.player, 0.5)
    else:
        bluff_rate = 1 - self._reliability(prior_bet.player, outcomes)
    threshold = self._threshold(bluff_rate)
    ...

def _threshold(self, bluff_rate: float) -> float:
    # Equivalent to original: 0.30 - (reliability - 0.5) * 0.30
    # with reliability = 1 - bluff_rate
    return 0.30 + (bluff_rate - 0.5) * 0.30
```

`_reliability()` is kept as the fallback path, not deleted.

### Zara

**Change:** `_bluff_rate(player, outcomes)` is replaced by a stats lookup.

```python
def algo(self, hand, prior_bet, total_dice, bet_history, outcomes, stats=None):
    ...
    if stats is not None:
        bluff_rate = stats.bluff_rate.get(prior_bet.player, 0.5)
    else:
        bluff_rate = self._bluff_rate(prior_bet.player, outcomes)
    if self._prob_bet_holds(...) < self._threshold(bluff_rate):
        return None
    ...
```

`_bluff_rate()` helper is kept as the fallback path.

### Sloane

**Change:** Three helpers replaced by stats lookups.

```python
def algo(self, hand, prior_bet, total_dice, bet_history, outcomes, stats=None):
    ...
    if stats is not None:
        face_bluff_rate = stats.bluff_rate_by_face.get(prior_bet.player, {}).get(prior_bet.face, 0.5)
        reliability = 1 - face_bluff_rate
        delta_bias = (0.5 - reliability) * 0.2

        delta_momentum = (1.0 - stats.current_round_velocity) * 0.1

        mean_qty = stats.mean_held_quantity_by_face.get(prior_bet.player, {}).get(prior_bet.face, 0)
        if mean_qty > 0:
            ratio = prior_bet.quantity / mean_qty
            delta_sig = min(0.1, (ratio - 1.5) * 0.05) if ratio > 1.5 else 0.0
        else:
            delta_sig = 0.0
    else:
        delta_bias = self._calculate_delta_bias(prior_bet.player, prior_bet.face, outcomes)
        delta_momentum = self._calculate_delta_momentum(bet_history, game, round_num)
        delta_sig = self._calculate_delta_signature(
            prior_bet.player, prior_bet.face, prior_bet.quantity, outcomes
        )
    ...
```

All three `_calculate_*` helpers are kept as the fallback path.

### Remy

**Change:** Four helpers replaced by stats lookups.

```python
def _threshold(self, bidder, face, total_dice, bet_history, outcomes, game, round_num, stats=None):
    base = 0.30

    if stats is not None:
        bluff_rate = stats.bluff_rate.get(bidder, 0.5)
        bias_adj = self._bias_adjustment_from_stats(bidder, face, stats)
        vel_adj = self._velocity_adjustment(stats.current_round_velocity)
    else:
        bluff_rate = self._bluff_rate(bidder, outcomes)
        bias_adj = self._bias_adjustment(bidder, face, outcomes)
        velocity = self._round_velocity(bet_history, game, round_num)
        vel_adj = self._velocity_adjustment(velocity)

    bluff_offset = (bluff_rate - 0.5) * 0.30
    endgame_adj = -0.05 if total_dice <= 10 else 0.0
    return max(0.10, base + bluff_offset + bias_adj + vel_adj + endgame_adj)

def _bias_adjustment_from_stats(self, player: str, face: int, stats) -> float:
    if stats.rounds_with_hand.get(player, 0) < 2:
        return 0.0
    observed_rate = stats.revealed_hand_frequency.get(player, {}).get(face, 0.0)
    expected_rate = 2 / 6 if face != 1 else 1 / 6
    bias = observed_rate - expected_rate
    return -max(-0.08, min(0.08, bias * 0.4))
```

`algo()` passes `stats` through to `_threshold()`. All original scan-based helpers are kept as the fallback path.

---

## 4. README Documentation

Add the following to the `algo` inputs table in the Player API section:

| Parameter | Type                | Description                                                                                                                                                                                                                                                                                                                            |
| --------- | ------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `stats`   | `GameStats \| None` | Pre-computed opponent statistics. Present only if your `algo` declares a 6th parameter. Use it instead of scanning `bet_history` or `outcomes` — those lists grow to tens of thousands of entries by game 1000 and scanning them on every turn will make your player slow. See `game/components/stats.py` for the full attribute list. |

Add a short callout below the table:

> **Performance note:** If your strategy looks at `bet_history` or `outcomes`, declare `stats=None` as a 6th parameter and use `GameStats` instead. A full scan of `outcomes` at game 1000 iterates ~15,000 entries — done on every turn, that makes the last games in a series ~2,000× slower than the first.

---

## 5. Testing

- `tests/test_stats.py` (new): unit tests for `GameStats` update logic — verify that `bluff_rate`, `current_round_velocity`, `revealed_hand_frequency`, and `mean_held_quantity_by_face` are correct after a sequence of synthetic updates.
- `tests/test_main.py`: add a test that a player declaring 6 args receives a non-None `stats` object.
- Existing player tests: the 5 non-migrated players (`Diego`, `Alice`, `Bruno`, `Cleo`, `Finn`) require no new tests — their code does not change.
- For migrated players: run the existing series tests; no behavioural change is expected (the stats-path computations are algebraically equivalent to the scan-path).

---

## 6. Out of Scope

- Timeout enforcement (separate spec)
- Exposing `GameStats` via a public API for external consumers
- Persisting stats across games (stats reset at the start of each `run_series()` call)
