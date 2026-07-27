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
| <img src="https://www.gravatar.com/avatar/9d7a2fcd3b902c71412b196c29f5ba95?d=identicon&f=y&s=64" width="64" height="64"> Littlefinger | 17.6 | 885 | 16.6 | 1490 | 9000 |
| <img src="https://www.gravatar.com/avatar/76fdf124f5765d774886a793d5023f32?d=identicon&f=y&s=64" width="64" height="64"> Varys | 14.0 | 800 | 22.4 | 1570 | 7000 |
| <img src="https://www.gravatar.com/avatar/39c6087277499978d0500bb0205419d1?d=identicon&f=y&s=64" width="64" height="64"> Ripley | 12.4 | 1908 | 14.7 | 1908 | 13000 |
| <img src="https://res.cloudinary.com/hdyiihba/image/upload/w_64,h_64,c_fill/The_Merovingian.png" width="64" height="64"> The Merovingian | 12.0 | 1740 | 13.4 | 1740 | 13000 |
| <img src="https://res.cloudinary.com/dfcgw5cr6/image/upload/w_64,h_64,c_fill/The_Oracle.gif" width="64" height="64"> The Oracle | 11.4 | 1892 | 14.6 | 1892 | 13000 |
| <img src="https://www.gravatar.com/avatar/f68b87e0e12c96cc8ec181aa48e4e9b5?d=identicon&f=y&s=64" width="64" height="64"> EvilStewie | 9.8 | 1484 | 11.4 | 1484 | 13000 |
| <img src="https://www.gravatar.com/avatar/4d0a927fbe8ecbf7e9d05deea69a694f?d=identicon&f=y&s=64" width="64" height="64"> Shwimp | 8.6 | 1132 | 10.0 | 1495 | 15000 |
| <img src="https://res.cloudinary.com/dfcgw5cr6/image/upload/w_64,h_64,c_fill/Deep_Thought.jpg" width="64" height="64"> Deep Thought | 7.7 | 1261 | 10.2 | 1431 | 14000 |

### Championship
| Player | Season W% | Wins in CH | Win % Total | Total Wins | Games |
|--------|-----------|----------------|-------------|------------|-------|
| <img src="https://res.cloudinary.com/rzifhdkf/image/upload/w_64,h_64,c_fill/HAL_9000.png" width="64" height="64"> HAL 9000 | Relegated | 292 | 10.1 | 1520 | 15000 |
| <img src="https://www.gravatar.com/avatar/28c4ac8b8ecc3772ff3d22f9bf6c737a?d=identicon&f=y&s=64" width="64" height="64"> Peter Beter | 11.6 | 1078 | 9.5 | 1428 | 15000 |
| <img src="https://www.gravatar.com/avatar/8eb6692d51ca57e7464df1cb61624c89?d=identicon&f=y&s=64" width="64" height="64"> Columbo | 11.6 | 1125 | 11.9 | 1790 | 15000 |
| <img src="https://www.gravatar.com/avatar/d51be008f389672257bcaa7b722a3df8?d=identicon&f=y&s=64" width="64" height="64"> Peter Griffin | 10.8 | 1425 | 10.4 | 1566 | 15000 |
| <img src="https://res.cloudinary.com/dfcgw5cr6/image/upload/w_64,h_64,c_fill/Cal_Culatid.jpg" width="64" height="64"> Cal Culatid | 10.6 | 1219 | 14.5 | 2176 | 15000 |
| <img src="https://res.cloudinary.com/hdyiihba/image/upload/w_64,h_64,c_fill/Sloane_Avery.png" width="64" height="64"> Sloane | 10.5 | 1457 | 11.2 | 1457 | 13000 |
| <img src="https://www.gravatar.com/avatar/4fb845c67d91bcb3178498fc6fe1fedc?d=identicon&f=y&s=64" width="64" height="64"> Diego | 10.2 | 1323 | 10.2 | 1323 | 13000 |
| <img src="https://www.gravatar.com/avatar/b4eed5a89f11670e6c411cab8aa2b5a7?d=identicon&f=y&s=64" width="64" height="64"> Stewie | 9.8 | 1494 | 11.0 | 1546 | 14000 |

### Level 1
| Player | Season W% | Wins in L1 | Win % Total | Total Wins | Games |
|--------|-----------|----------------|-------------|------------|-------|
| <img src="https://res.cloudinary.com/hdyiihba/image/upload/w_64,h_64,c_fill/Zara.png" width="64" height="64"> Zara | Relegated | 0 | 9.9 | 1286 | 13000 |
| <img src="https://res.cloudinary.com/dfcgw5cr6/image/upload/w_64,h_64,c_fill/Honest_Abe.jpg" width="64" height="64"> Honest Abe | 27.2 | 3520 | 26.2 | 3667 | 14000 |
| <img src="https://res.cloudinary.com/hdyiihba/image/upload/w_64,h_64,c_fill/Nuke_LaLoosh.png" width="64" height="64"> Nuke LaLoosh | 26.5 | 4056 | 23.9 | 4543 | 19000 |
| <img src="https://res.cloudinary.com/hdyiihba/image/upload/w_64,h_64,c_fill/Eva_Longoria.png" width="64" height="64"> Eva | 25.8 | 1751 | 18.6 | 2421 | 13000 |
| <img src="https://res.cloudinary.com/hdyiihba/image/upload/w_64,h_64,c_fill/Remy_Beasley.png" width="64" height="64"> Remy | 19.0 | 2998 | 21.7 | 3044 | 14000 |
| <img src="https://res.cloudinary.com/hdyiihba/image/upload/w_64,h_64,c_fill/Finn_Carter.png" width="64" height="64"> Finn | 14.8 | 2291 | 17.6 | 2291 | 13000 |
| <img src="https://res.cloudinary.com/hdyiihba/image/upload/w_64,h_64,c_fill/Meg_Griffin.png" width="64" height="64"> Meg Griffin | 14.5 | 2223 | 17.1 | 2223 | 13000 |
| <img src="https://www.gravatar.com/avatar/64489c85dc2fe0787b85cd87214b3810?d=identicon&f=y&s=64" width="64" height="64"> Alice | 14.5 | 1610 | 12.4 | 1610 | 13000 |
| <img src="https://www.gravatar.com/avatar/17ad55a9b8384777496330d23e59d520?d=identicon&f=y&s=64" width="64" height="64"> Rick Sanchez | 13.3 | 2184 | 16.8 | 2184 | 13000 |
| <img src="https://www.gravatar.com/avatar/9b2b78033ecf0401a2feab5b4ba7462e?d=identicon&f=y&s=64" width="64" height="64"> Bruno | 10.3 | 1703 | 13.1 | 1703 | 13000 |
| <img src="https://res.cloudinary.com/hdyiihba/image/upload/w_64,h_64,c_fill/Liar_Liar.png" width="64" height="64"> Liar², Pants on Fire | 3.2 | 583 | 4.5 | 583 | 13000 |
| <img src="https://res.cloudinary.com/hdyiihba/image/upload/w_64,h_64,c_fill/Topper.png" width="64" height="64"> Topper | 1.6 | 354 | 2.7 | 354 | 13000 |
| <img src="https://www.gravatar.com/avatar/6e1def9bfa26327930ba900d46f8c9b3?d=identicon&f=y&s=64" width="64" height="64"> Cleo | 1.3 | 275 | 2.1 | 275 | 13000 |

### Quarter Leaderboard

| Player | Tier | PRM W% | CH W% | L1 W% | Total W% | Games |
|--------|------|--------|-------|-------|----------|-------|
| <img src="https://www.gravatar.com/avatar/76fdf124f5765d774886a793d5023f32?d=identicon&f=y&s=64" width="64" height="64"> Varys | Premier | 16.0 | 26.0 | 51.0 | 22.4 | 7000 |
| <img src="https://www.gravatar.com/avatar/39c6087277499978d0500bb0205419d1?d=identicon&f=y&s=64" width="64" height="64"> Ripley | Premier | 14.7 | — | — | 14.7 | 13000 |
| <img src="https://res.cloudinary.com/dfcgw5cr6/image/upload/w_64,h_64,c_fill/The_Oracle.gif" width="64" height="64"> The Oracle | Premier | 14.6 | — | — | 14.6 | 13000 |
| <img src="https://res.cloudinary.com/hdyiihba/image/upload/w_64,h_64,c_fill/The_Merovingian.png" width="64" height="64"> The Merovingian | Premier | 13.4 | — | — | 13.4 | 13000 |
| <img src="https://www.gravatar.com/avatar/9d7a2fcd3b902c71412b196c29f5ba95?d=identicon&f=y&s=64" width="64" height="64"> Littlefinger | Premier | 12.6 | 15.8 | 44.7 | 16.6 | 9000 |
| <img src="https://www.gravatar.com/avatar/f68b87e0e12c96cc8ec181aa48e4e9b5?d=identicon&f=y&s=64" width="64" height="64"> EvilStewie | Premier | 11.4 | — | — | 11.4 | 13000 |
| <img src="https://res.cloudinary.com/dfcgw5cr6/image/upload/w_64,h_64,c_fill/Deep_Thought.jpg" width="64" height="64"> Deep Thought | Premier | 9.7 | 17.0 | — | 10.2 | 14000 |
| <img src="https://res.cloudinary.com/rzifhdkf/image/upload/w_64,h_64,c_fill/HAL_9000.png" width="64" height="64"> HAL 9000 | Championship | 9.4 | 14.6 | — | 10.1 | 15000 |
| <img src="https://www.gravatar.com/avatar/4d0a927fbe8ecbf7e9d05deea69a694f?d=identicon&f=y&s=64" width="64" height="64"> Shwimp | Premier | 8.7 | 18.1 | — | 10.0 | 15000 |
| <img src="https://www.gravatar.com/avatar/b4eed5a89f11670e6c411cab8aa2b5a7?d=identicon&f=y&s=64" width="64" height="64"> Stewie | Championship | 5.2 | 11.5 | — | 11.0 | 14000 |
| <img src="https://www.gravatar.com/avatar/28c4ac8b8ecc3772ff3d22f9bf6c737a?d=identicon&f=y&s=64" width="64" height="64"> Peter Beter | Championship | 5.0 | 13.5 | — | 9.5 | 15000 |
| <img src="https://www.gravatar.com/avatar/d51be008f389672257bcaa7b722a3df8?d=identicon&f=y&s=64" width="64" height="64"> Peter Griffin | Championship | 4.7 | 11.9 | — | 10.4 | 15000 |
| <img src="https://www.gravatar.com/avatar/8eb6692d51ca57e7464df1cb61624c89?d=identicon&f=y&s=64" width="64" height="64"> Columbo | Championship | 4.2 | 11.2 | 26.9 | 11.9 | 15000 |
| <img src="https://res.cloudinary.com/hdyiihba/image/upload/w_64,h_64,c_fill/Sloane_Avery.png" width="64" height="64"> Sloane | Championship | — | 11.2 | — | 11.2 | 13000 |
| <img src="https://res.cloudinary.com/dfcgw5cr6/image/upload/w_64,h_64,c_fill/Cal_Culatid.jpg" width="64" height="64"> Cal Culatid | Championship | — | 10.2 | 31.9 | 14.5 | 15000 |
| <img src="https://www.gravatar.com/avatar/4fb845c67d91bcb3178498fc6fe1fedc?d=identicon&f=y&s=64" width="64" height="64"> Diego | Championship | — | 10.2 | — | 10.2 | 13000 |
| <img src="https://res.cloudinary.com/hdyiihba/image/upload/w_64,h_64,c_fill/Zara.png" width="64" height="64"> Zara | Level 1 | — | 9.9 | — | 9.9 | 13000 |
| <img src="https://res.cloudinary.com/hdyiihba/image/upload/w_64,h_64,c_fill/Eva_Longoria.png" width="64" height="64"> Eva | Level 1 | — | 9.6 | 29.2 | 18.6 | 13000 |
| <img src="https://res.cloudinary.com/hdyiihba/image/upload/w_64,h_64,c_fill/Nuke_LaLoosh.png" width="64" height="64"> Nuke LaLoosh | Level 1 | — | 8.1 | 31.2 | 23.9 | 19000 |
| <img src="https://res.cloudinary.com/dfcgw5cr6/image/upload/w_64,h_64,c_fill/Honest_Abe.jpg" width="64" height="64"> Honest Abe | Level 1 | — | 7.3 | 29.3 | 26.2 | 14000 |
| <img src="https://res.cloudinary.com/hdyiihba/image/upload/w_64,h_64,c_fill/Remy_Beasley.png" width="64" height="64"> Remy | Level 1 | — | 4.6 | 23.1 | 21.7 | 14000 |
| <img src="https://res.cloudinary.com/hdyiihba/image/upload/w_64,h_64,c_fill/Finn_Carter.png" width="64" height="64"> Finn | Level 1 | — | — | 17.6 | 17.6 | 13000 |
| <img src="https://res.cloudinary.com/hdyiihba/image/upload/w_64,h_64,c_fill/Meg_Griffin.png" width="64" height="64"> Meg Griffin | Level 1 | — | — | 17.1 | 17.1 | 13000 |
| <img src="https://www.gravatar.com/avatar/17ad55a9b8384777496330d23e59d520?d=identicon&f=y&s=64" width="64" height="64"> Rick Sanchez | Level 1 | — | — | 16.8 | 16.8 | 13000 |
| <img src="https://www.gravatar.com/avatar/9b2b78033ecf0401a2feab5b4ba7462e?d=identicon&f=y&s=64" width="64" height="64"> Bruno | Level 1 | — | — | 13.1 | 13.1 | 13000 |
| <img src="https://www.gravatar.com/avatar/64489c85dc2fe0787b85cd87214b3810?d=identicon&f=y&s=64" width="64" height="64"> Alice | Level 1 | — | — | 12.4 | 12.4 | 13000 |
| <img src="https://res.cloudinary.com/hdyiihba/image/upload/w_64,h_64,c_fill/Liar_Liar.png" width="64" height="64"> Liar², Pants on Fire | Level 1 | — | — | 4.5 | 4.5 | 13000 |
| <img src="https://res.cloudinary.com/hdyiihba/image/upload/w_64,h_64,c_fill/Topper.png" width="64" height="64"> Topper | Level 1 | — | — | 2.7 | 2.7 | 13000 |
| <img src="https://www.gravatar.com/avatar/6e1def9bfa26327930ba900d46f8c9b3?d=identicon&f=y&s=64" width="64" height="64"> Cleo | Level 1 | — | — | 2.1 | 2.1 | 13000 |

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
