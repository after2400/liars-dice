---
title: Nuke LaLoosh — Player Design
date: 2026-06-14
status: approved
---

# Nuke LaLoosh — Player Design

## Personality

Nuke LaLoosh is the raw-talent, zero-discipline fastball pitcher from Bull Durham. He has the stuff to compete but throws heat when he should think, and thinks he can blow it past anyone. His signature move is opening on 1s — a disruptive pitch that turns wilds off for the entire round, making every subsequent bid harder to hold. He doesn't always throw the heater, though; occasionally he mixes in a changeup to keep opponents off balance.

**Target performance:** Comfortable CH player (~20-30% win rate), promotable to PRM with occasional good runs (~14-18%). Comparable to Remy/Finn at their CH-level peaks. Not a leader-tier threat.

---

## Opening Bid (the Fastball / Changeup)

**75% of the time:** Nuke opens on 1s — his fastball. This turns wilds off for the round (`wilds=False` propagates to `bet_grader`), structurally disrupting everyone else's expected counts for non-1 faces.

Opening quantity for 1s:

```
max(own_1s + 1, round(own_1s + unseen * (1/6) * 0.7))
```

- Always bets at least one more than he holds personally (`own_1s + 1`)
- Scales up with game size via the probability term
- Early game: probability term dominates, bid is sound-to-conservative
- Endgame: `+1 flat` dominates, bid is a genuine heater — he always throws a little harder than the math says to

**25% of the time:** Changeup — opens on his best non-1 face using Diego's standard formula (`own + unseen * 2/6 * 0.7`). Same logic Diego uses; the surprise is the pitch selection, not the mechanics.

---

## Liar Calling

Uses Diego's exact binomial `_prob_bet_holds`:

```
P(X >= need) where X ~ Binomial(unseen, p)
p = 1/6 for face==1, 2/6 otherwise (wilds)
```

Threshold is a tunable constant `CALL_THRESHOLD`. Three variants to test empirically:

| Variant | `CALL_THRESHOLD` | Raise when backed |
| ------- | ---------------- | ----------------- |
| A       | 0.20             | +1                |
| B       | 0.30             | +2                |
| C       | 0.20             | +2                |

Diego uses 0.30/+1. Nuke at 0.20 is slower to doubt (more permissive). Nuke at +2 is more aggressive when he has backing.

---

## Raising

Diego-style logic, with raise size controlled by `RAISE_WHEN_BACKED`:

1. If holding the prior face (including wilds): raise quantity by `RAISE_WHEN_BACKED`
2. Else shift to a higher face we hold at same quantity
3. Last resort: raise quantity by 1 on same face regardless

---

## Implementation Plan

1. Implement `players/nuke.py` as a single class with `CALL_THRESHOLD` and `RAISE_WHEN_BACKED` constants
2. Run all three variants via `just simulate` and compare win rates
3. Set constants to the winning variant; delete the others from comments
4. Register Nuke in the leaderboard starting at L1

---

## What Makes Nuke Distinct

No existing player combines:

- A signature disruptive opening move (1s, wilds-off)
- Occasional pitch mixing (changeup to keep opponents off balance)
- Diego-quality probability engine underneath
- Tuned aggression constants rather than pure mechanical escalation

Topper/Pyro are mechanical escalators with no probability. Cleo has randomness but no structure. Nuke has structure (Diego's binomial) with personality layered on top.
