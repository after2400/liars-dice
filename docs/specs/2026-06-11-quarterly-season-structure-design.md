# Quarterly Season Structure Design

_Status: in-progress brainstorm — several open decisions noted below_

## Context

As the league grows toward 64+ players (external contributors + owner-authored bots),
the current continuous-accumulation model breaks down: long-tenured players accrue
statistical advantages independent of actual skill. This design introduces a quarterly
cadence that hard-resets stats and re-seeds tiers via a tournament.

---

## Target State: 64-Player League

Tier capacities at full scale:

| Tier | Capacity | Notes                  |
| ---- | -------- | ---------------------- |
| PRM  | 8        | Premier                |
| CH   | 8        | Championship           |
| L1   | 16       | League One             |
| DED  | 32       | Inactive / dead letter |

> **Deferred:** The L1=16 / DED=32 sizing has game-engine implications (current max
> `TOP_N` is 8). Requires its own brainstorm/plan before those tiers can run
> regular-season games at full capacity.

---

## Quarterly Reset

At the end of each quarter, **all `tier_stats` are hard-zeroed**. Players start the
new quarter with no accumulated wins, games, or win%. Tier placements are also reset
— they are re-assigned by the tournament (below), not carried forward.

What "end of quarter" means in terms of calendar alignment with weekly Monday runs is
TBD (e.g., last Monday of the quarter, or first Monday after a quarter boundary).

---

## Quarterly Tournament

The tournament re-seeds all players into tiers for the new quarter, eliminating
longevity bias.

### Seeding

Players are ranked 1–64 by their end-of-quarter tier standings, read top-to-bottom:
PRM #1 = seed 1, PRM #2 = seed 2, …, DED #32 = seed 64. No formula — just the
existing leaderboard order.

### Pool Formation (S-curve / serpentine)

64 players are assigned to 8 pools of 8 using S-curve seeding, ensuring each pool
contains one player from every strength band:

```
Pool 1: seeds  1, 16, 17, 32, 33, 48, 49, 64
Pool 2: seeds  2, 15, 18, 31, 34, 47, 50, 63
Pool 3: seeds  3, 14, 19, 30, 35, 46, 51, 62
Pool 4: seeds  4, 13, 20, 29, 36, 45, 52, 61
Pool 5: seeds  5, 12, 21, 28, 37, 44, 53, 60
Pool 6: seeds  6, 11, 22, 27, 38, 43, 54, 59
Pool 7: seeds  7, 10, 23, 26, 39, 42, 55, 58
Pool 8: seeds  8,  9, 24, 25, 40, 41, 56, 57
```

Each pool's top seed (1–8) leads a balanced draw; no pool is systematically stronger
or weaker than another.

### Pool Play

Each pool runs **1000 games** with all 8 players competing simultaneously — same
engine and format as a regular tier season.

### Tier Placement (direct mapping)

| Pool finish | New tier |
| ----------- | -------- |
| 1st         | PRM      |
| 2nd         | CH       |
| 3rd – 4th   | L1       |
| 5th – 8th   | DED      |

No cross-pool playoff. The S-curve seeding ensures pools are balanced, so pool
position is a meaningful result on its own. A lucky PRM qualifier is self-correcting:
they face top competition every week and drop back within a quarter.

---

## GitHub Tracking Issues

Each quarter gets its own GitHub issue (e.g., "Q3 2026 Season"). The quarterly
transition:

1. Creates the new quarter's tracking issue
2. Posts the tournament summary as the first comment
3. Subsequent weekly season runs append to that issue (same append-only pattern as
   today)

The current issue reference needs to be stored somewhere accessible to
`run_season.py` — likely a field in `leaderboard.yaml` or a small config file.
**Open decision:** exact storage location.

Global stats, when designed, get their own separate issue.

---

## Implementation Approach

**Leaning toward A+C hybrid — not yet finalized:**

- **Approach A** (standalone): new `run-tournament.yml` workflow + `run_tournament.py`
  script; regular `run-season.yml` gets a guard that skips if a tournament ran that day
- **Approach C** (reset script): a `reset_season.py` handles archive stub + pool
  formation + tournament + tier placement as a clean data-flow unit
- **Hybrid**: dedicated tournament workflow (A's separation) that calls a
  `reset_season.py` internally (C's clean data flow + archive stub ready to wire in)

Decision to be made before implementation begins.

---

## Scaled-Down Version (< 64 players)

The 64-player / 8-pool format assumes full scale. A scaled-down tournament format for
the transition period (current ~11 players → 64) is **not yet designed**. Options
include smaller pool counts, different tier capacities, or skipping the tournament
until a minimum player count is reached. **Deferred.**

---

## Deferred to Separate Brainstorms

| Topic                             | Notes                                                                           |
| --------------------------------- | ------------------------------------------------------------------------------- |
| Global / career ranking formula   | All-time ranking, tier-weighted wins, tenure adjustment, yearly top-N snapshots |
| Archive format                    | What gets stored per-quarter, how it feeds global ranking                       |
| Per-player history for algos      | Machine-readable quarterly stats accessible via `GameStats` or similar          |
| liars-dice-2 overflow repo        | Handling DED list when it grows unwieldy                                        |
| L1=16 / DED=32 game-engine sizing | Regular-season games with 16+ players per tier                                  |
