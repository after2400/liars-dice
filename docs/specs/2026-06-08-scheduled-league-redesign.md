# Scheduled League Redesign

## Goal

Decouple game execution from player registration. PRs add players to the league; a daily scheduled job runs all tier games, evaluates results, and updates the leaderboard. This eliminates race conditions, prevents CI spam, and makes the league feel like a real ongoing competition rather than a per-PR event.

## Current State

- Games are triggered by player PRs
- A new player immediately plays their entry game on PR open
- Promotion/relegation is evaluated per-PR
- Stats are cumulative per-tier (already implemented)
- Solo-game guard prevents games with <2 players (already implemented)

---

## Architecture

### Two workflows replace the current one

**`register-player.yml`** — triggered by PR to `main` touching `players/*`

1. Validate the PR (see PR Validation)
2. Detect entry tier (see Entry Tier Logic)
3. Register player in `leaderboard.yaml` (see Leaderboard Schema)
4. Commit leaderboard update to the PR branch
5. Auto-merge the PR
6. No games run

**`run-season.yml`** — triggered on a daily schedule (`0 9 * * *` UTC — 4am EST, 5am EDT)

1. Run each active tier in bottom-up order: **inactive → L1 → CH → PRM**
   - Active = has ≥2 players
   - Run `N_GAMES` (250) games per tier
   - Evaluate results: apply promotions/relegations before running the next tier up
2. Commit a single leaderboard update with `[skip ci]`
3. Post a summary to a designated tracking issue

---

## Tier Structure

Capacities scale with `TOP_N` (GitHub repo variable, starts at 4, max 8):

| Tier     | Capacity    | Notes                                     |
| -------- | ----------- | ----------------------------------------- |
| PRM      | `TOP_N`     | Premier Division                          |
| CH       | `TOP_N`     | Championship                              |
| L1       | `2 × TOP_N` | League One                                |
| inactive | unlimited   | Daily game with up to `2 × TOP_N` players |

---

## Player Class Spec

Player files must define a class with a `make_bid` method. The `name` attribute is optional:

```python
class Fred:
    name = "Fred the Magnificent"  # optional display name, max 25 chars
                                   # defaults to class name if omitted

    def make_bid(self, ...):
        ...
```

- `name` must be ≤25 characters, alphanumeric + spaces + basic punctuation
- Parentheses are reserved (used for the username suffix in display)
- The class name (i.e. `Fred`) is the stable identifier — it must match the filename (`fred.py`)

---

## Leaderboard Schema

The leaderboard key is the **class name** (stable, immutable). Display name and GitHub username are stored as separate fields:

```yaml
players:
  Fred: # key = class name
    display_name: Fred the Magnificent
    github_username: after2400
    date_added: "2026-06-08T00:00:00Z"
    tier: PRM
    tier_since: "2026-06-08T00:00:00Z"
    times_inactive: 0 # replaces times_last_in_l1
    tier_stats:
      PRM:
        wins: 60
        games: 100
        win_pct: 60.0
```

Full display name rendered at output time: `"{display_name} ({github_username})"`,
e.g. `"Fred the Magnificent (after2400)"`.

**`times_inactive`** replaces `times_last_in_l1` — incremented each time a player is
relegated to inactive.

---

## PR Validation

PRs touching `players/` fall into two mutually exclusive modes. A PR that mixes
deletions with additions or modifications is rejected outright.

### Addition / modification (exactly one file)

| Diff filter                                                 | Case              | Action                |
| ----------------------------------------------------------- | ----------------- | --------------------- |
| Added, class name not in leaderboard                        | New player        | Register + auto-merge |
| Added, class name already in leaderboard                    | Duplicate name    | Reject with comment   |
| Modified, `github_username` matches `github.actor`          | Algorithm update  | Validate + auto-merge |
| Modified, `github_username` mismatch and actor is not admin | Unauthorized edit | Reject with comment   |
| Modified, actor is admin                                    | Admin override    | Validate + auto-merge |

### Deletion (one or more files, admin batch allowed)

| Case                                                           | Action                                                   |
| -------------------------------------------------------------- | -------------------------------------------------------- |
| Actor is admin                                                 | Remove all deleted players from leaderboard + auto-merge |
| Actor is not admin, deleted file belongs to actor              | Self-removal + auto-merge                                |
| Actor is not admin, any deleted file belongs to another player | Reject with comment                                      |

**Admin check:** query the GitHub API for the actor's repository permission level.
Admin = `admin` permission role.

```bash
gh api repos/${{ github.repository }}/collaborators/${{ github.actor }}/permission \
  --jq '.permission == "admin"'
```

**Deleted player handling:** player is removed entirely from `leaderboard.yaml`.
All stats are discarded. If the player was mid-tier, they simply won't appear in
the next scheduled run.

**Author verification (modifications):** look up `github_username` by class name in
the leaderboard. Compare to `github.actor`. No string parsing needed.

**Name updates:** a modified file may change the `name` attribute freely. The workflow
updates `display_name` in the leaderboard. Class name, `github_username`, and all
stats are unchanged.

---

## Entry Tier Logic

New players always enter at **L1 or above — never inactive**. They enter the lowest
active tier that has capacity:

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

**First player in L1:** If L1 currently has 0 players, it is not active. The new player
enters CH instead. In their first scheduled run they compete in CH — if they win they
promote to PRM; if they lose they are relegated to L1, which now has its first resident
waiting for a second player.

A player registered mid-day plays in the next scheduled run — no immediate game.

---

## Promotion and Relegation

Tiers run bottom-up in the same daily job so promotions are available when the tier
above runs. All movements are applied immediately (no deferred pending_relegation)
within a single scheduled run.

### Per-tier rules (per daily run)

**inactive:**

- Up to `2 × TOP_N` players participate (selection criteria: see Open Questions)
- Top player → promoted to L1 (if L1 has capacity)
- No relegation out of inactive

**L1:**

- Top player → promoted to CH (if CH has capacity)
- Bottom player → relegated to inactive; `times_inactive` incremented

**CH:**

- Top player → promoted to PRM (if PRM has capacity)
- Bottom player → relegated to L1 (if L1 has capacity)

**PRM:**

- Bottom player → relegated to CH (if CH has capacity)
- No promotion out of PRM

### Capacity-based movement

Promotions and relegations move as many players as needed to restore each tier to
capacity — not a fixed "1 up, 1 down". If multiple new players registered in a tier
since the last run, the tier may be overcapacity and must shed the excess downward
before the tier above promotes into it.

### Tiebreak

Within a run: equal wins → more historical `tier_stats[tier].games` (longer proven
record) → earlier `tier_since` (longer tenure at current tier).

---

## Game Engine Changes

The game engine currently uses `p.name` (the `name` attribute) as the leaderboard
lookup key. With class name as the stable key, this must change:

- Add a `class_name` property to the player base spec: `type(self).__name__`
- Game engine uses `class_name` for leaderboard lookups and win tracking
- `name` / `display_name` is used only for display output

---

## Stats and Visibility

### Per-tier cumulative stats (already implemented)

`tier_stats` tracks wins/games/win_pct per tier independently. Win% in the leaderboard
table reflects the player's **current tier** only.

### Per-run results (to implement)

Each daily run posts a summary showing:

- Standings table with cumulative tier win%
- This run's results (wins out of `N_GAMES`, win% for this run only)
- Promotions and relegations that occurred

---

## Decisions

| Topic              | Decision                                                                                                   |
| ------------------ | ---------------------------------------------------------------------------------------------------------- |
| Schedule           | `0 9 * * *` UTC (4am EST / 5am EDT)                                                                        |
| Churn              | Single-run results for promotion/relegation; revisit with rolling average if too volatile                  |
| Tier capacities    | PRM = `TOP_N`, CH = `TOP_N`, L1 = `2 × TOP_N`, inactive = unlimited (capped at `2 × TOP_N` for daily game) |
| Max TOP_N          | 8 (giving PRM=8, CH=8, L1=16)                                                                              |
| N_GAMES            | 250 per tier per daily run                                                                                 |
| Leaderboard key    | Class name (stable); display name stored separately                                                        |
| `times_last_in_l1` | Renamed to `times_inactive`                                                                                |

---

## Open Questions

### Which inactive players participate when inactive > `2 × TOP_N`?

Options: most recently relegated (LIFO), best historical win%, or rotate fairly.
Recommendation: start with all inactive players (no cap) and add a cap only if the
inactive pool becomes unwieldy.

### Run ordering: can a player play twice in one day?

If a player tops the inactive run and promotes to L1, they could play in the L1 game
the same day. Same applies at L1→CH and CH→PRM boundaries. This is intentional —
it rewards strong performance — but means a player could play up to 4 games in one
day in an extreme case.

### What if a tier has exactly 1 player?

The solo-game guard (already implemented) exits cleanly with no stats updated. That
player waits until another player joins their tier.

---

## Rollout

1. Update player class spec and game engine (`class_name` property, leaderboard lookup)
2. Migrate leaderboard schema (`display_name`, `github_username`, `times_inactive`)
3. Implement `register-player.yml` (validation, registration, auto-merge)
4. Implement `run-season.yml` (scheduled bottom-up tier runner)
5. Retire current `liars-dice.yml`
6. Update tests throughout
