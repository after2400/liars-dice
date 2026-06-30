# Deep Thought: Opening Obfuscation + Leader Targeting Design

**Date:** 2026-06-30
**Player:** `players/deepthought.py`

## Problem

Deep Thought always opens on its best-supported face. Opponents using opening-bid
inference (`_round_opening_bids` + `_infer_held`) — including EvilStewie and Deep
Thought itself — treat this as a reliable signal. Over many rounds, the opening
becomes fully readable: open on 5s with quantity 4 → opponent credits us with ~2
real 5s and adjusts `_prob_holds` accordingly.

Separately, Deep Thought has no concept of which opponent is most dangerous. The
EV scan treats inducing a failed call from the table leader the same as inducing
one from a single-die desperate player.

## Goals

1. **Opening obfuscation:** break the predictability of Deep Thought's opening face
   selection without introducing randomness. Make inference engines build incorrect
   priors about our hand.

2. **Leader targeting:** when the table's strongest opponent (most dice) sits
   immediately after us, bias the raise EV scan to prefer bids that induce their
   failed challenge — tactically eliminating the most dangerous player first.

## Non-Goals

- Randomness of any kind in decision-making.
- Targeting players not immediately after us in seat order.
- Changing the call/challenge logic.

---

## Design

### 1. Opening Obfuscation

**New constant:**
```python
OBFUSCATION_THRESHOLD = 1  # max support gap to trigger face swap
```

**Logic (replaces the `prior_bet is None` block):**

1. Compute support for every face 2–6: `support(f) = hand.count(f) + hand.count(1)`
2. Sort faces by support descending → `best_face`, `second_face`
3. If `support(best_face) - support(second_face) <= OBFUSCATION_THRESHOLD`:
   - Open on `second_face` using `own = support(second_face)`
4. Otherwise: open on `best_face` as today

Quantity formula is unchanged: `max(1, round(own + unseen * (2/6) * multiplier))`.

**Effect:** when two faces are within 1 die of each other, Deep Thought opens on
the weaker face. Opponents infer we hold that face; we hold more of the other for
confident mid-round raises. When the best face has a clear 2+ die advantage, no
obfuscation occurs — no cost to position.

**Why deterministic:** the trigger is hand composition. We only obfuscate when the
alternate face is a genuinely plausible open, so no coin flip is needed.

---

### 2. Leader Identification

**New method: `_identify_target(ctx) -> str | None`**

```python
def _identify_target(self, ctx: GameContext) -> str | None:
    counts = ctx.stats.dice_counts if ctx.stats else {}
    candidates = {p: c for p, c in counts.items() if p != self.name and c > 0}
    return max(candidates, key=candidates.__getitem__) if candidates else None
```

Returns the name of the opponent with the most dice. Called once per turn, no
new persistent state required.

---

### 3. Target-Pressure Raise Bias

**New constant:**
```python
TARGET_EV_WIN_BONUS = 0.3  # added to EV_WIN_CALL when target is next player
```

**Logic in `_best_raise`:**

`_best_raise` receives one new parameter: `target_is_next: bool`.

EV formula per candidate bid:
```
ev_win = self.EV_WIN_CALL + (TARGET_EV_WIN_BONUS if target_is_next else 0.0)
ev = (1-p_call)*EV_SAFE + p_call*p_holds*ev_win + p_call*(1-p_holds)*EV_LOSE_CALL
```

No other changes to the scan. The bonus naturally elevates bids with high `p_holds`
(well-supported for us) and high `p_call` (suspicious-looking to the target) — the
exact profile of a "trap" bid.

**Call site in `algo`:**
```python
target = self._identify_target(ctx)
next_p = self._next_player(ctx)
target_is_next = (target is not None and target == next_p)
...
quantity, face = self._best_raise(
    hand, prior_bet, total_dice, opening_bids, bluff_rates,
    next_p, base_p_call, target_is_next=target_is_next
)
```

---

## New Constants Summary

| Constant | Value | Purpose |
|---|---|---|
| `OBFUSCATION_THRESHOLD` | `1` | Max support gap to trigger face swap on open |
| `TARGET_EV_WIN_BONUS` | `0.3` | EV bonus for inducing target's failed call |

Both are class-level tunables, consistent with all existing Deep Thought constants.

---

## Testing Plan

Run each change independently and combined against the baseline using the quarter
simulation. Gate: only keep what improves placement/win rate by a margin that
clears the noise floor.

```bash
# Baseline
just simulate-quarter

# With obfuscation only (comment out targeting)
just simulate-quarter

# With targeting only (comment out obfuscation)
just simulate-quarter

# Combined
just simulate-quarter
```

Compare Deep Thought's win %, promotions, and dice-loss rate across runs. Use
`N_GAMES=500` or higher for statistical confidence. Revert any feature that
regresses performance.
