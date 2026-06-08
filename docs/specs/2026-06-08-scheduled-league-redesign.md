# Scheduled League Redesign

## Goal

Decouple game execution from player registration. PRs add players to the league; a daily scheduled job runs all tier games, evaluates results, and updates the leaderboard. This eliminates race conditions, prevents CI spam, and makes the league feel like a real ongoing competition rather than a per-PR event.

## Current State

- Games are triggered by player PRs
- A new player immediately plays their entry game on PR open
- Promotion/relegation is evaluated per-PR
- Stats are cumulative per-tier (already implemented)
- Solo-game guard prevents games with <2 players (already implemented)

## Architecture

### Two workflows replace the current one

**`register-player.yml`** — triggered by PR to `main` touching `players/*`
1. Validate: exactly one new `.py` file added
2. Detect entry tier (see Entry Tier Logic)
3. Add player to `leaderboard.yaml` at that tier with zeroed `tier_stats`
4. Commit leaderboard update to the PR branch
5. Auto-merge the PR
6. No games run

**`run-season.yml`** — triggered on a daily schedule (cron)
1. For each active tier in order (PRM → CH → L1):
   - Active = has ≥2 players
   - Run 250 games (`N_GAMES` repo variable)
   - Evaluate results: sort by wins, apply promotion/relegation
2. Commit single leaderboard update
3. Post summary comment to a designated issue (or update a pinned discussion)

### Tier structure

Capacities scale with `TOP_N` (GitHub repo variable, starts at 4, max 8):

| Tier     | Capacity   | Notes                        |
|----------|------------|------------------------------|
| PRM      | `TOP_N`    | Premier Division             |
| CH       | `TOP_N`    | Championship                 |
| L1       | `2×TOP_N`  | League One                   |
| inactive | unlimited  | Eliminated from L1           |

## Entry Tier Logic

New players enter at the **lowest active tier that has capacity**:

```
if L1 is active and L1 has capacity:
    enter L1
elif CH is active and CH has capacity:
    enter CH
else:
    enter PRM
```

Active = tier has ≥1 existing player (will have ≥2 once the new player joins).
Capacity = current player count < tier capacity.

A player registered mid-day plays in the next scheduled run — no immediate game.

## Promotion and Relegation

After each scheduled tier run, results determine movement. All tiers run in the same daily job; promotions and relegations from one tier affect the next tier's game in the **same run** (applied in order: L1 first, then CH, then PRM — bottom up so promotions are available when the higher tier runs).

### Per-tier rules (per daily run)

**L1:**
- Top player → promoted to CH (if CH has capacity)
- Bottom player → inactive (if L1 is at capacity)

**CH:**
- Top player → promoted to PRM (if PRM has capacity)
- Bottom player → relegated to L1 (if L1 has capacity)

**PRM:**
- Bottom player → relegated to CH (if CH has capacity)
- No promotion out of PRM

### Capacity-based, not fixed-count

Promotions and relegations are determined by how far each tier is from its capacity, not a fixed "1 up, 1 down" rule. If 3 new players registered in CH since the last run, CH may be over capacity and needs to shed players downward before PRM promotes into it.

**Example with TOP_N=4:**
- PRM at 5 (overcapacity by 1): relegate bottom 1 to CH
- CH at 4 (at capacity): before accepting PRM relegation, promote top 1 to PRM to make room
- Evaluate in bottom-up order to ensure space exists before movement

### Ties

Tiebreak within a run: players with equal wins are ranked by historical `tier_stats[tier].games` descending (more games = more proven). Secondary tiebreak: `tier_since` ascending (longer tenure = higher rank).

## Stats and Visibility

### Per-tier cumulative stats (already implemented)

`tier_stats` in `leaderboard.yaml` tracks wins/games/win_pct per tier independently. A player who plays in both CH and PRM has separate records for each. Win% in the leaderboard table reflects the player's **current tier** only.

### Per-run results (to implement)

Each daily run stores the session results so the leaderboard comment shows:
- Standings table with cumulative tier win%
- This run's results (wins out of 250, win% for this run only)
- Any promotions/relegations that occurred

This gives two views: long-term form and yesterday's performance.

## Decisions

### Schedule

`0 9 * * *` UTC — 4am EST (standard time). Runs 1 hour late (5am) during EDT. GitHub Actions has no native timezone awareness; this is the closest fixed UTC expression to 4am America/New_York year-round.

### Churn rate

Start with single-run results for promotion/relegation decisions. Revisit with a rolling average if churn feels too high in practice.

## Open Questions

### Run ordering within a day

If tiers run bottom-up (L1 → CH → PRM) in the same job, a player promoted from L1 to CH could theoretically play in the CH game in the same daily run. This is a feature, not a bug — it rewards strong performance. However, it means the CH game sees a different roster than when the job started. This is acceptable.

### What if a tier has exactly 1 player?

The solo-game guard (already implemented) exits cleanly. That player waits until another player joins their tier. No stats are updated.

## GitHub Actions Notes

- `N_GAMES` and `TOP_N` remain GitHub repo variables
- The scheduled workflow runs even if no new players registered — tiers with ≥2 players always get a game
- `[skip ci]` on the leaderboard commit remains to avoid re-triggering the register workflow
- The register workflow still needs branch protection to validate player files before merge
- Auto-merge on the register workflow fires immediately after validation (no game to wait for)

## Rollout

1. Implement `register-player.yml` (stripped-down current workflow — validation + registration only)
2. Implement `run-season.yml` (scheduled daily game runner)
3. Remove game-running steps from current `liars-dice.yml`
4. Reset leaderboard to current clean state (already done)
5. Set initial schedule (daily at a fixed UTC time)
