# Relegation Cascade Settlement — Design

**Date:** 2026-06-11
**Status:** Approved (brainstorming)

## Problem

The daily season driver (`.github/scripts/run_season.py` → `game.components.leaderboard.apply_season_results`) runs tiers **bottom-up** (`inactive → L1 → CH → PRM`) and applies promotions and relegations **immediately, per tier**.

Promotions move _up_ into tiers that have not run yet, so they are handled correctly in-pass: a promoted player joins the higher tier and plays it the same night.

Relegations move _down_ into tiers that have **already run**. A tier therefore decides its own relegations before it knows whether the tier above will push a player back down into it. The current rule (`apply_season_results`, "relegate only if remaining players exceed capacity after promotion", added in PR #13) evaluates a tier at its own run-time, when it looks exactly full, and relegates no one — even though the tier above is about to drop a player into it.

### Observed failure (run of 2026-06-11, from the balanced state PRM=4 / CH=4 / L1=3)

| Tier | Runs with              | Promotes   | Relegates (current code)                      | Leaves tier at |
| ---- | ---------------------- | ---------- | --------------------------------------------- | -------------- |
| L1   | Cleo, Pyro, Topper (3) | Cleo → CH  | —                                             | 2              |
| CH   | +Cleo = 5              | Remy → PRM | none (headcount 4 == capacity when evaluated) | 4              |
| PRM  | +Remy = 5              | —          | Remy → CH                                     | 4              |

End state: **CH = 5** (Remy dumped back in, nobody sent down), **L1 = 2**. The missing movement is **CH → L1**: Cleo was promoted _up_ into CH and Remy was pushed back _down_ into CH, so CH is over by one and should send its weakest player (Cleo, dead last at 0.4%) down to L1. The capacity guard cannot see the incoming relegation, so the imbalance is never reconciled.

The structural cause: **a bottom-up single pass cannot cascade relegations**, because every relegation lands in a tier that has already finished its own settlement.

## Goal

After each nightly run, the ladder is **balanced in the same run**: every tier sits at or below its capacity, with overflow cascaded all the way down. Specifically the run must reproduce the intuitive "each middle tier swaps one up and one down" steady state, while never relegating a player out of a tier that still has empty seats (no over-draining in partial/low-population states).

## Tier capacities (unchanged)

| Tier     | Capacity                            |
| -------- | ----------------------------------- |
| PRM      | `TOP_N`                             |
| CH       | `TOP_N`                             |
| L1       | `TOP_N × 2` (roomy feeder division) |
| inactive | unbounded (overflow)                |

`L1 = TOP_N × 2` is deliberate: players reach `inactive` only when L1 itself overflows. The "swap exactly one" behavior therefore applies to the **PRM↔CH and CH↔L1** boundaries; the **L1→inactive** boundary relegates only when L1 genuinely exceeds `TOP_N × 2`.

## Approach: bottom-up promotions, then a top-down settlement pass

Promotions stay exactly where they are (in-pass, bottom-up). Relegations move into a single **top-down settlement** that runs **after all games are played**, when every tier's real headcount is known. Because PRM's relegation lands in CH _before_ settlement processes CH, the cascade completes in one pass.

### Phase A — bottom-up game runs + promotions (unchanged)

For `tier in [inactive, L1, CH, PRM]`:

- Skip tiers with `< 2` players.
- Run the games, accumulate cumulative `tier_stats`.
- Promote the top-ranked player to the tier above (if one exists), applied immediately and **persisted to `leaderboard.yaml`** so the next tier up plays them this same night.

`apply_season_results` keeps its stats-update and promotion logic and **loses its relegation block entirely**.

### Phase B — top-down settlement (new)

A new function `settle_relegations(tier_results, top_n, path)` runs once after the Phase-A loop. It reads the post-promotion leaderboard and walks tiers **top-down** (`PRM → CH → L1`):

For each tier `T`:

1. Recompute `residents` = players currently in `T` (this includes anyone relegated into `T` earlier in this same settlement pass).
2. `excess = len(residents) − capacity(T)`. If `excess <= 0`, continue.
3. Build the **candidate pool**: residents who **played `T` this season** (`name in tier_results[T]`) and are **not parachutists** (see below). Rank worst-first by `(this_season_wins ASC, total_tier_games ASC, tier_since DESC)`.
4. Relegate the `excess` worst candidates to the tier below:
   - Set `tier = tier_below`, `tier_since = now`.
   - If `tier_below == "inactive"`, increment `times_inactive`.
   - Record the player as a **parachutist** of `tier_below` (so the next iteration does not re-drop them).
   - Append `Relegated: {display_name} → {tier_below}` to the movements list.
5. Write `leaderboard.yaml` once after the full top-down walk. Return the movements list.

### Parachutist protection (the crucial rule)

A **parachutist** is a player relegated into a tier _during this settlement pass_. Parachutists hold a protected seat: they are excluded from that tier's candidate pool, so a player dropped from PRM into CH is never dropped a second division (CH → L1) in the same night. They get their season in the new tier instead.

This is what makes the cascade land on the right player. In the worked example, when PRM drops Remy into CH and CH is then over capacity, Remy is protected, so CH relegates its worst **player**, Cleo (who actually played CH and finished last), down to L1.

A player **promoted into** a tier this season (e.g. Cleo, L1 → CH) is _not_ protected — they played the tier, so they are an ordinary candidate. "You are only relegated for losing in a tier you actually played."

### Ranking and tiebreaks

Within a tier's candidate pool, worst-first order is `(this_season_wins ASC, total_tier_games ASC, tier_since DESC)`: fewest wins this season first; ties broken toward the least-experienced and most-recently-arrived player. `this_season_wins` comes from `tier_results[T][name]` (games-per-player are equal within a tier run, so raw win count is a valid ranking).

### Edge cases

- **Excess exceeds the candidate pool** (a tier is over capacity but every remaining resident is a parachutist or did not play): this is only reachable if a tier received more than one drop from above in a single night, which cannot happen while every tier above relegates at most one. We therefore do **not** handle it — `settle_relegations` asserts the candidate pool is large enough to cover the excess (e.g. `assert len(candidates) >= excess`). If the assertion ever fires, an upstream invariant has broken and we want the loud failure, not a silent guess.
- **Skipped tier receiving a drop:** a tier with `< 2` players cannot exceed `TOP_N` (for `TOP_N ≥ 2`) even after receiving one parachutist, so settlement simply finds `excess <= 0` and does nothing. No special handling needed.
- **`tier_results` missing a tier** (tier skipped this run): its players are treated as non-playing; combined with the skipped-tier point above, the tier is not over capacity, so settlement does nothing and the assertion is not reached.

## Components and changes

### `game/components/leaderboard.py`

- **`apply_season_results`**: remove the relegation block (current lines ~224–242) and the now-unused `tier_below` lookup. Keep stats accumulation, the unconditional top-player promotion, `total_runs`/`last_updated` bookkeeping, and the per-call file write. Continues to return the (promotion-only) movements list.
- **`settle_relegations(tier_results, top_n, path)`**: new function as specified in Phase B.
- **Delete the dead code this design supersedes or that is unreachable at runtime** (each is referenced only by tests today; nothing else in the codebase imports them):
  - `apply_pending_relegation` and the `pending_relegation` list handling — the deferred-relegation mechanism this design explicitly rejects.
  - `update_leaderboard` — the older, superseded season driver (its `pending_relegations` / `last_place` parameters belong to abandoned approaches).
  - `detect_phase` — phase detection that nothing calls; phase-gated movement is not part of this (or any current) behavior.

### `.github/scripts/run_season.py`

- After the bottom-up tier loop, call `settle_relegations(tier_results, top_n, lb_path)` once and print each returned movement (e.g. under a `[settle]` line). Promotion movements continue to print per-tier during the loop; relegation movements now print together after the loop.

### Tests (`tests/`)

- Rework the four relegation-specific `apply_season_results` tests (`..._no_relegation_from_prm_at_exact_capacity`, `..._no_relegation_when_promotion_restores_capacity`, `..._relegates_when_truly_overcrowded`, `..._no_relegation_when_tier_below_capacity`) to target `settle_relegations`.
- Keep the promotion tests for `apply_season_results` (promotion behavior is unchanged); assert it no longer relegates.
- New `settle_relegations` tests:
  1. **Cascade in one pass** — the worked example: PRM=5, CH=5 (one promoted-in player who flopped + one parachutist), L1 under capacity → ends PRM=4, CH=4, L1+1, correct players moved.
  2. **Parachutist protection** — a player dropped from above is _not_ re-dropped; the worst native player drops instead.
  3. **No relegation at/under capacity.**
  4. **L1 → inactive only when L1 > TOP_N × 2**, and `times_inactive` increments on that drop.
  5. **Movement strings use disambiguated display names** (mirrors the existing display-name test).
- Remove the tests for the deleted functions: `apply_pending_relegation`, `update_leaderboard`, and `detect_phase`. Drop any test fixtures left unused after their removal.

Run the full suite with `uv run pytest -v` (collects `tests/` and `examples/tests/`).

## Out of scope

- **Promotion logic** is unchanged. Only relegation moves to the settlement pass.
- **Phase-gated movement** as a behavior. Deleting `detect_phase` removes the only (unused) scaffolding for it; whether early-population runs should suppress promotion/relegation is a separate design question, not this bug.

## Worked example (today's real state: PRM=4, CH=4, L1=3, inactive=0; TOP_N=4)

**Phase A (bottom-up, promotions):**

- `inactive`: 0 players → skip.
- `L1` (Cleo, Pyro, Topper): promote Cleo → CH. L1 = {Pyro, Topper}.
- `CH` (Alice, Bruno, Finn, Remy + Cleo = 5): promote Remy → PRM. CH played = {Alice, Bruno, Finn, Cleo}.
- `PRM` (Diego, Eva, Sloane, Zara + Remy = 5): top tier, no promotion.

**Phase B (top-down settlement):**

- `PRM`: 5 > 4, excess 1. Worst player = Remy (10.6%). Relegate Remy → CH (parachutist of CH). PRM = 4.
- `CH`: now 5 (Alice, Bruno, Finn, Cleo + Remy-parachutist), excess 1. Candidates exclude Remy (parachutist); worst player = Cleo (0.4%). Relegate Cleo → L1. CH = 4.
- `L1`: 3 < 8, excess ≤ 0. No drop. L1 = {Pyro, Topper, Cleo} = 3.

**End: PRM=4, CH=4, L1=3, inactive=0.** Balanced in one run. Cleo bounces back for flopping in CH; Remy gets his PRM-to-CH landing and a CH season. No player is sent to inactive while L1 has open seats.
