# Quarterly Season Structure Design

_Status: design complete — ready for implementation planning_

## Context

As the league grows toward 64+ players (external contributors + owner-authored bots),
the current continuous-accumulation model breaks down: long-tenured players accrue
statistical advantages independent of actual skill. This design introduces a quarterly
cadence that hard-resets stats and re-seeds tiers via a tournament.

---

## Target State: 64-Player League

Tier capacities at full scale:

| Tier | Capacity | Notes           |
| ---- | -------- | --------------- |
| PRM  | 8        | Premier         |
| CH   | 8        | Championship    |
| L1   | 16       | League One      |
| DED  | 32       | Dead (inactive) |

> **Deferred:** The L1=16 / DED=32 sizing has game-engine implications (current max
> `TOP_N` is 8). Requires its own brainstorm/plan before those tiers can run
> regular-season games at full capacity.

---

## Quarterly Reset

At the end of each quarter, **all `tier_stats` are hard-zeroed**. Players start the
new quarter with no accumulated wins, games, or win%. Tier placements are also reset
— they are re-assigned by the tournament (below), not carried forward.

The reset runs on the **first Monday of the new quarter** — the regular season runs
normally through the last Monday of the old quarter, then the tournament fires the
following week to open the new quarter. Example 2026 dates: Apr 6, Jul 6, Oct 5, Jan 4.

---

## Quarterly Tournament (Full Scale: 64 Players)

The tournament re-seeds all players into tiers for the new quarter, eliminating
longevity bias. See "Scaled-Down Version" for behavior during the transition period.

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

The current issue number is stored as `current_season_issue` at the top level of
`leaderboard.yaml`. The quarterly reset script writes this field when it creates the
new tracking issue; `run_season.py` reads it when appending weekly results.

Global stats, when designed, get their own separate issue.

---

## Implementation Approach

**Single workflow + idempotent reset script.**

- **`run-monday.yml`** — replaces `run-season.yml`. Triggers on schedule (every Monday)
  and via `workflow_dispatch` with a `force_tournament` boolean input. At the top,
  checks whether today is a tournament Monday (first Monday of a new quarter) or
  `force_tournament` is set; branches into either `reset_season.py` or `run_season.py`.
  One entry point, one place the tournament/season decision lives — eliminates any
  cross-workflow guard.

- **`reset_season.py`** — owns the full quarterly transition as a clean, **idempotent**
  data pipeline. Each step is a no-op if already completed, so the script is safe to
  re-run after a failure. Steps in order:
  1. Zero all `tier_stats` in `leaderboard.yaml`
  2. Compute new tier capacities from current player count (per capacity table)
  3. Form pools: `ceil(N / 8)` pools, S-curve seeded by current standings
  4. Run tournament games (1000 games per pool)
  5. Merge standings by win%, assign tier placements top-down
  6. Create new quarter's GitHub tracking issue, write `current_season_issue` to
     `leaderboard.yaml`
  7. Post tournament summary as first issue comment

- **`run_season.py`** — unchanged except it no longer needs a tournament guard.

---

## Tier Capacity by Player Count

Growth priority: **L1 fills first, then PRM/CH expand together, then DED opens.**

- **Phase 1 (N ≤ 24):** PRM=4, CH=4 fixed; each new player goes to L1 until L1=16.
- **Phase 2 (24 < N ≤ 32):** L1 stays at 16; PRM and CH grow symmetrically (in pairs).
- **Phase 3 (N > 32):** PRM=8, CH=8, L1=16 all fixed; each new player goes to DED.

> **Note:** Variable tier capacities mean the promotion/relegation engine will need
> updates to calculate correctly (currently hardcoded to `TOP_N`).

| Players | PRM | CH  | L1  | DED | Notes                                 |
| ------- | --- | --- | --- | --- | ------------------------------------- |
| 8       | 4   | 4   | 0   | 0   | 2 active tiers                        |
| 9       | 4   | 4   | 1   | 0   | L1 opens                              |
| 11      | 4   | 4   | 3   | 0   | **current**                           |
| 12      | 4   | 4   | 4   | 0   |                                       |
| 16      | 4   | 4   | 8   | 0   |                                       |
| 20      | 4   | 4   | 12  | 0   |                                       |
| 24      | 4   | 4   | 16  | 0   | L1 full; Phase 2 begins               |
| 26      | 5   | 5   | 16  | 0   |                                       |
| 28      | 6   | 6   | 16  | 0   |                                       |
| 30      | 7   | 7   | 16  | 0   |                                       |
| 32      | 8   | 8   | 16  | 0   | all active tiers full; Phase 3 begins |
| 33      | 8   | 8   | 16  | 1   | DED opens                             |
| 64      | 8   | 8   | 16  | 32  | **target**                            |

At odd player counts in Phase 2 (e.g., 25 players), the extra player holds in L1
until the next player joins, at which point both PRM and CH grow by 1 together.

**Mid-quarter registration:** new players enter the lowest active tier that still has
capacity (L1 if not full, otherwise CH, otherwise PRM). They are seeded into the next
quarterly tournament from their end-of-quarter standing.

## Scaled-Down Version (< 64 players): Tournament

Single-stage format. Engine limit of 8 players per pool.

### Pool Formation

- Pool count: `ceil(N / 8)` — fewest pools needed to keep all pools at ≤ 8 players
- Pool sizes: distributed as evenly as possible (sizes differ by at most 1)
- Seeding: players ranked by current tier standings (PRM #1 → DED #last), then
  assigned to pools via S-curve so each pool gets a balanced mix of strong and weak

### Pool Play

Each pool runs 1000 games. All players are then **ranked globally by win%**, and
tier slots filled top-to-bottom per the capacity table.

**Cross-pool win% caveat:** players in smaller pools have a slightly higher expected
win rate (fewer opponents per game). Accepted — pool sizes differ by at most 1, and
tournament placement is only the initial seeding for the quarter; a misseeded player
self-corrects within one regular season.

### Example pool layouts

| N   | Pools                        | Sizes   |
| --- | ---------------------------- | ------- |
| 8   | 1                            | 8       |
| 11  | 2                            | 6/5     |
| 16  | 2                            | 8/8     |
| 24  | 3                            | 8/8/8   |
| 32  | 4                            | 8/8/8/8 |
| 64  | → full-scale S-curve (8 × 8) | —       |

The scaled-down format transitions naturally to the full-scale format at 64 players
(8 pools of 8), with no structural break.

---

## Deferred to Separate Brainstorms

| Topic                             | Notes                                                                           |
| --------------------------------- | ------------------------------------------------------------------------------- |
| Global / career ranking formula   | All-time ranking, tier-weighted wins, tenure adjustment, yearly top-N snapshots |
| Archive format                    | What gets stored per-quarter, how it feeds global ranking                       |
| Per-player history for algos      | Machine-readable quarterly stats accessible via `GameStats` or similar          |
| liars-dice-2 overflow repo        | Handling DED list when it grows unwieldy                                        |
| L1=16 / DED=32 game-engine sizing | Regular-season games with 16+ players per tier                                  |
