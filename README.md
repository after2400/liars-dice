# Liar's Dice League

A Python engine for running Liar's Dice games between algorithmic players. Players compete in a tiered league — submit a PR to join, and a weekly scheduled run plays the games and updates standings (extra runs trigger automatically when a player file changes).

Interested in competing? See [CONTRIBUTING.md](CONTRIBUTING.md) · Game rules: [RULES.md](RULES.md)

## Current Standings

<!-- prettier-ignore-start -->
<!-- leaderboard-start -->
### Premier
| Player | Win % in PRM | Wins in PRM | Win % Total | Total Wins | Games |
|--------|----------------|----------------|-------------|------------|-------|
| Diego | 27.0 | 1174 | 27.0 | 1174 | 4350 |
| Zara | 25.9 | 1034 | 27.2 | 1358 | 5000 |
| Sloane | 25.4 | 762 | 27.6 | 1380 | 5000 |
| Eva | 21.6 | 433 | 29.8 | 1490 | 5000 |

### Championship
| Player | Win % in CH | Wins in CH | Win % Total | Total Wins | Games |
|--------|----------------|----------------|-------------|------------|-------|
| Finn | 31.2 | 312 | 18.0 | 767 | 4250 |
| Remy | 23.5 | 941 | 20.9 | 1047 | 5000 |
| Bruno | 15.2 | 305 | 12.9 | 572 | 4450 |
| Alice | 14.6 | 437 | 14.6 | 651 | 4450 |

### Level 1
| Player | Win % in L1 | Wins in L1 | Win % Total | Total Wins | Games |
|--------|----------------|----------------|-------------|------------|-------|
| Cleo | 47.1 | 471 | 10.8 | 482 | 4450 |
| Topper | 44.4 | 444 | 44.4 | 444 | 1000 |
| Liar², Pants on Fire | 8.5 | 85 | 8.5 | 85 | 1000 |

<!-- leaderboard-end -->
<!-- prettier-ignore-end -->

_Updated weekly (Mondays at 9am UTC) or whenever a player file is added/modified. Full history in the [season tracking issue](https://github.com/after2400/liars-dice/issues/4)._

---

## How It Works

Two workflows replace the old per-PR game model:

**`register-player.yml`** — triggered when a PR touches `players/`

- Validates the player file (class name matches filename, display name ≤ 25 chars)
- Registers the player in `leaderboard.yaml` at the appropriate entry tier
- Commits the leaderboard update and auto-merges the PR
- No games run immediately

**`run-season.yml`** — cron fires daily at 9am UTC; a guard job decides whether to actually run

- Runs on Mondays (weekly cadence) or when any `players/*.py` file was added/modified in the last 24h; `workflow_dispatch` always runs
- Plays `N_GAMES` (default 1000) games in each active tier, bottom-up: `inactive → L1 → CH → PRM`
- Promotions and relegations are applied between tiers (so a player promoted from L1 can compete in CH the same day)
- Commits the updated leaderboard and posts a summary to the season tracking issue

A tier is skipped if it has fewer than 2 players.

---

## Tier Structure

Capacities scale with `TOP_N` (repo variable, default 4, max 8):

| Tier     | Capacity    | Notes                                 |
| -------- | ----------- | ------------------------------------- |
| PRM      | `TOP_N`     | Premier Division — top of the table   |
| CH       | `TOP_N`     | Championship                          |
| L1       | `2 × TOP_N` | League One                            |
| inactive | unlimited   | Plays separately; top player promotes |

**Entry tier:** new players enter the lowest active tier that has capacity (L1 if possible, else CH, else PRM). A player registered mid-day plays in the next scheduled run.

**Promotion / relegation (per season run):**

- Top player in each tier promotes to the tier above
- Bottom player(s) relegate to the tier below
- `times_inactive` increments each time a player is relegated to inactive

---

## Project Structure

```
game/
  __main__.py          # entry point, logging, player selection, --tier filter
  validate.py          # player file validator (python -m game.validate <file>)
  components/
    script.py          # game loop and round orchestration
    bets.py            # Bet class, bet_validator, bet_grader
    series.py          # series runner and results formatter
    leaderboard.py     # leaderboard read/write, apply_season_results
    stats.py           # GameStats incremental stats (passed as 6th algo arg)
    utils.py           # player loader

players/               # one .py file per player — see full list on GitHub
  ...                  # https://github.com/after2400/liars-dice/tree/main/players

.github/
  workflows/
    register-player.yml  # PR validation, registration, auto-merge
    run-season.yml       # weekly/conditional season runner (guard + run jobs)
    release.yml          # PSR — bumps version, regenerates CHANGELOG, creates GitHub Release
    lint.yml             # ruff + commitlint on push/PR
  scripts/
    register_player.py   # validates player file, writes leaderboard entry
    run_season.py        # bottom-up tier runner, writes season summary
    reset_season.py      # quarterly tournament reset and pool runner
    season_utils.py      # shared leaderboard I/O and date utilities
    lb_owner.py          # looks up github_username by class name
    lb_delete.py         # removes players from leaderboard by file path
    lb_update_name.py    # validates and updates display_name on modification

.Justfile                # local dev recipes (just develop / pytest / lint / simulate-*)
leaderboard.yaml         # source of truth — tier, stats, github_username per player
```
