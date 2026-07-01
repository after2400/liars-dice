# Liar's Dice League

A Python engine for running Liar's Dice games between algorithmic players. Players compete in a tiered league — submit a PR to join, and a weekly scheduled run plays the games and updates standings (extra runs trigger automatically when a player file changes).

_This project is based on the foundational work and initial implementation by [Zach Austin](https://github.com/zachaustin01)._

Interested in competing? **[Visit the Wiki](https://github.com/after2400/liars-dice/wiki)** — rules, player API, and how to submit a bot. For local dev setup see [CONTRIBUTING.md](CONTRIBUTING.md).

## Current Standings

<!-- prettier-ignore-start -->
<!-- leaderboard-start -->
### Premier
| Player | Season W% | Wins in PRM | Win % Total | Total Wins | Games |
|--------|-----------|----------------|-------------|------------|-------|
| Ripley | 17.3 | 173 | 30.3 | 909 | 3000 |
| The Merovingian | 16.2 | 818 | 27.0 | 1620 | 6000 |
| EvilStewie | 15.4 | 2501 | 17.6 | 2822 | 16000 |
| The Oracle | 14.7 | 320 | 28.3 | 1133 | 4000 |
| Deep Thought | 13.6 | 2142 | 15.3 | 2142 | 14000 |
| Peter Beter | 6.6 | 2309 | 15.3 | 2600 | 17000 |
| Peter Griffin | 5.8 | 2299 | 13.5 | 2299 | 17000 |
| Sloane | 5.7 | 4113 | 17.3 | 7794 | 45000 |

### Championship
| Player | Season W% | Wins in CH | Win % Total | Total Wins | Games |
|--------|-----------|----------------|-------------|------------|-------|
| Nuke LaLoosh | Relegated | 552 | 15.8 | 4268 | 27000 |
| Columbo | 12.4 | 1015 | 15.2 | 1524 | 10000 |
| Stewie | 12.0 | 485 | 17.6 | 5114 | 29000 |
| Diego | 10.5 | 2727 | 17.2 | 6409 | 37350 |
| Zara | 9.2 | 4110 | 18.1 | 6525 | 36000 |
| Cal Culatid | 8.9 | 2659 | 16.9 | 4223 | 25000 |
| Honest Abe | 8.6 | 2662 | 13.6 | 3135 | 23000 |
| Eva | 8.1 | 5485 | 18.5 | 6863 | 37000 |

### Level 1
| Player | Season W% | Wins in L1 | Win % Total | Total Wins | Games |
|--------|-----------|----------------|-------------|------------|-------|
| Remy | Relegated | 4441 | 16.7 | 8346 | 50000 |
| Finn | 12.0 | 3977 | 16.7 | 6717 | 40250 |
| Rick Sanchez | 11.1 | 3599 | 16.4 | 3599 | 22000 |
| Bruno | 9.0 | 3294 | 12.3 | 4249 | 34450 |
| Alice | 8.1 | 4325 | 15.3 | 5418 | 35450 |
| Meg Griffin | 7.6 | 600 | 10.0 | 600 | 6000 |
| Topper | 2.3 | 2387 | 7.7 | 2387 | 31000 |
| Liar², Pants on Fire | 2.0 | 1020 | 3.9 | 1020 | 26000 |
| Cleo | 0.4 | 1699 | 4.8 | 1716 | 35450 |

### Quarter Leaderboard

| Player | Tier | PRM W% | CH W% | L1 W% | Total W% | Games |
|--------|------|--------|-------|-------|----------|-------|
| The Merovingian | Premier | 20.4 | 33.4 | 46.8 | 27.0 | 6000 |
| Zara | Championship | 20.1 | 17.1 | — | 18.1 | 36000 |
| Diego | Championship | 18.1 | 16.0 | — | 17.2 | 37350 |
| Ripley | Premier | 17.3 | 26.1 | 47.5 | 30.3 | 3000 |
| Eva | Championship | 17.2 | 18.9 | — | 18.5 | 37000 |
| EvilStewie | Premier | 16.7 | 32.1 | — | 17.6 | 16000 |
| Stewie | Championship | 16.7 | 24.2 | 28.8 | 17.6 | 29000 |
| The Oracle | Premier | 16.0 | 36.9 | 44.4 | 28.3 | 4000 |
| Deep Thought | Premier | 15.3 | — | — | 15.3 | 14000 |
| Alice | Level 1 | 14.8 | 12.6 | 16.0 | 15.3 | 35450 |
| Peter Beter | Premier | 14.4 | 29.1 | — | 15.3 | 17000 |
| Sloane | Premier | 14.2 | 23.0 | — | 17.3 | 45000 |
| Finn | Level 1 | 14.0 | 12.7 | 20.9 | 16.7 | 40250 |
| Peter Griffin | Premier | 13.5 | — | — | 13.5 | 17000 |
| Nuke LaLoosh | Championship | 13.3 | 27.6 | 52.1 | 15.8 | 27000 |
| Cal Culatid | Championship | 12.8 | 16.6 | 26.5 | 16.9 | 25000 |
| Bruno | Level 1 | 10.9 | 13.8 | 12.2 | 12.3 | 34450 |
| Remy | Level 1 | 10.6 | 13.2 | 22.2 | 16.7 | 50000 |
| Columbo | Championship | 7.2 | 16.9 | 29.3 | 15.2 | 10000 |
| Cleo | Level 1 | 1.1 | 0.3 | 5.5 | 4.8 | 35450 |
| Honest Abe | Championship | — | 12.7 | 23.6 | 13.6 | 23000 |
| Rick Sanchez | Level 1 | — | — | 16.4 | 16.4 | 22000 |
| Meg Griffin | Level 1 | — | — | 10.0 | 10.0 | 6000 |
| Topper | Level 1 | — | — | 7.7 | 7.7 | 31000 |
| Liar², Pants on Fire | Level 1 | — | — | 3.9 | 3.9 | 26000 |

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
    stats.py           # GameStats incremental stats (optional algo arg, opt-in by name)
    utils.py           # player loader
  season/
    utils.py           # shared helpers: _load_lb, _save_lb, date/quarter utilities
  simulation/
    quarter.py         # simulate a full quarter locally (uv run python -m game.simulation.quarter)

players/               # one .py file per player — see full list on GitHub
  ...                  # https://github.com/after2400/liars-dice/tree/main/players

.github/
  workflows/
    register-player.yml      # PR validation, registration, auto-merge
    run-monday.yml           # weekly/conditional season runner (guard + run jobs)
    update-leaderboard.yml   # updates README standings on player file changes
    guard-non-player-prs.yml # blocks non-admin non-player PRs from auto-merge
    release.yml              # PSR — bumps version, regenerates CHANGELOG, creates GitHub Release
    lint.yml                 # ruff + commitlint on push/PR
  scripts/
    register_player.py   # validates player file, writes leaderboard entry
    run_season.py        # bottom-up tier runner, writes season summary
    reset_season.py      # quarterly tournament reset and pool runner
    lb_owner.py          # looks up github_username by class name
    lb_has_player.py     # checks whether a class name is registered
    lb_delete.py         # removes players from leaderboard by file path
    lb_update_player.py  # validates and updates display_name/avatar on modification

.Justfile                # local dev recipes (just develop / pytest / lint / simulate-*)
leaderboard.yaml         # source of truth — tier, stats, github_username per player
```
