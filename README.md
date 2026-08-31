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
| <img src="https://www.gravatar.com/avatar/9d7a2fcd3b902c71412b196c29f5ba95?d=identicon&f=y&s=64" width="64" height="64"> Littlefinger | 19.0 | 2243 | 17.8 | 2848 | 16000 |
| <img src="https://www.gravatar.com/avatar/76fdf124f5765d774886a793d5023f32?d=identicon&f=y&s=64" width="64" height="64"> Varys | 15.2 | 1761 | 18.1 | 2531 | 14000 |
| <img src="https://res.cloudinary.com/hdyiihba/image/upload/w_64,h_64,c_fill/The_Merovingian.png" width="64" height="64"> The Merovingian | 13.0 | 2500 | 12.5 | 2500 | 20000 |
| <img src="https://res.cloudinary.com/dfcgw5cr6/image/upload/w_64,h_64,c_fill/The_Oracle.gif" width="64" height="64"> The Oracle | 11.1 | 2724 | 13.6 | 2724 | 20000 |
| <img src="https://www.gravatar.com/avatar/39c6087277499978d0500bb0205419d1?d=identicon&f=y&s=64" width="64" height="64"> Ripley | 10.7 | 2725 | 13.6 | 2725 | 20000 |
| <img src="https://www.gravatar.com/avatar/f68b87e0e12c96cc8ec181aa48e4e9b5?d=identicon&f=y&s=64" width="64" height="64"> EvilStewie | 10.2 | 2179 | 10.9 | 2179 | 20000 |
| <img src="https://res.cloudinary.com/rzifhdkf/image/upload/w_64,h_64,c_fill/HAL_9000.png" width="64" height="64"> HAL 9000 | 7.3 | 1720 | 10.5 | 2622 | 25000 |
| <img src="https://www.gravatar.com/avatar/4d0a927fbe8ecbf7e9d05deea69a694f?d=identicon&f=y&s=64" width="64" height="64"> Shwimp | 7.0 | 1667 | 10.3 | 2578 | 25000 |

### Championship
| Player | Season W% | Wins in CH | Win % Total | Total Wins | Games |
|--------|-----------|----------------|-------------|------------|-------|
| <img src="https://res.cloudinary.com/dfcgw5cr6/image/upload/w_64,h_64,c_fill/Deep_Thought.jpg" width="64" height="64"> Deep Thought | Relegated | 334 | 9.8 | 2145 | 22000 |
| <img src="https://www.gravatar.com/avatar/28c4ac8b8ecc3772ff3d22f9bf6c737a?d=identicon&f=y&s=64" width="64" height="64"> Peter Beter | 12.0 | 1943 | 10.4 | 2293 | 22000 |
| <img src="https://www.gravatar.com/avatar/b4eed5a89f11670e6c411cab8aa2b5a7?d=identicon&f=y&s=64" width="64" height="64"> Stewie | 11.4 | 2119 | 12.9 | 2832 | 22000 |
| <img src="https://www.gravatar.com/avatar/8eb6692d51ca57e7464df1cb61624c89?d=identicon&f=y&s=64" width="64" height="64"> Columbo | 11.2 | 1836 | 11.4 | 2501 | 22000 |
| <img src="https://www.gravatar.com/avatar/d51be008f389672257bcaa7b722a3df8?d=identicon&f=y&s=64" width="64" height="64"> Peter Griffin | 10.5 | 2191 | 10.6 | 2332 | 22000 |
| <img src="https://res.cloudinary.com/hdyiihba/image/upload/w_64,h_64,c_fill/Sloane_Avery.png" width="64" height="64"> Sloane | 9.6 | 2145 | 10.7 | 2145 | 20000 |
| <img src="https://res.cloudinary.com/dfcgw5cr6/image/upload/w_64,h_64,c_fill/Cal_Culatid.jpg" width="64" height="64"> Cal Culatid | 8.2 | 1936 | 13.2 | 2893 | 22000 |
| <img src="https://res.cloudinary.com/hdyiihba/image/upload/w_64,h_64,c_fill/Eva_Longoria.png" width="64" height="64"> Eva | 8.1 | 1015 | 19.1 | 4204 | 22000 |

### Level 1
| Player | Season W% | Wins in L1 | Win % Total | Total Wins | Games |
|--------|-----------|----------------|-------------|------------|-------|
| <img src="https://res.cloudinary.com/dfcgw5cr6/image/upload/w_64,h_64,c_fill/Honest_Abe.jpg" width="64" height="64"> Honest Abe | Relegated | 5251 | 23.7 | 5685 | 24000 |
| <img src="https://www.gravatar.com/avatar/4fb845c67d91bcb3178498fc6fe1fedc?d=identicon&f=y&s=64" width="64" height="64"> Diego | 28.8 | 574 | 12.0 | 2402 | 20000 |
| <img src="https://res.cloudinary.com/hdyiihba/image/upload/w_64,h_64,c_fill/Nuke_LaLoosh.png" width="64" height="64"> Nuke LaLoosh | 26.2 | 5664 | 23.4 | 6320 | 27000 |
| <img src="https://res.cloudinary.com/hdyiihba/image/upload/w_64,h_64,c_fill/Zara.png" width="64" height="64"> Zara | 25.7 | 1888 | 15.9 | 3174 | 20000 |
| <img src="https://res.cloudinary.com/hdyiihba/image/upload/w_64,h_64,c_fill/Remy_Beasley.png" width="64" height="64"> Remy | 23.2 | 4303 | 20.7 | 4349 | 21000 |
| <img src="https://res.cloudinary.com/hdyiihba/image/upload/w_64,h_64,c_fill/Finn_Carter.png" width="64" height="64"> Finn | 15.1 | 3299 | 16.5 | 3299 | 20000 |
| <img src="https://www.gravatar.com/avatar/64489c85dc2fe0787b85cd87214b3810?d=identicon&f=y&s=64" width="64" height="64"> Alice | 12.8 | 2370 | 11.8 | 2370 | 20000 |
| <img src="https://www.gravatar.com/avatar/17ad55a9b8384777496330d23e59d520?d=identicon&f=y&s=64" width="64" height="64"> Rick Sanchez | 12.5 | 3230 | 16.2 | 3230 | 20000 |
| <img src="https://res.cloudinary.com/hdyiihba/image/upload/w_64,h_64,c_fill/Meg_Griffin.png" width="64" height="64"> Meg Griffin | 10.5 | 3189 | 15.9 | 3189 | 20000 |
| <img src="https://www.gravatar.com/avatar/9b2b78033ecf0401a2feab5b4ba7462e?d=identicon&f=y&s=64" width="64" height="64"> Bruno | 9.4 | 2279 | 11.4 | 2279 | 20000 |
| <img src="https://res.cloudinary.com/hdyiihba/image/upload/w_64,h_64,c_fill/Liar_Liar.png" width="64" height="64"> Liar², Pants on Fire | 3.7 | 779 | 3.9 | 779 | 20000 |
| <img src="https://res.cloudinary.com/hdyiihba/image/upload/w_64,h_64,c_fill/Topper.png" width="64" height="64"> Topper | 1.0 | 555 | 2.8 | 555 | 20000 |
| <img src="https://www.gravatar.com/avatar/6e1def9bfa26327930ba900d46f8c9b3?d=identicon&f=y&s=64" width="64" height="64"> Cleo | 0.6 | 317 | 1.6 | 317 | 20000 |

### Quarter Leaderboard

| Player | Tier | PRM W% | CH W% | L1 W% | Total W% | Games |
|--------|------|--------|-------|-------|----------|-------|
| <img src="https://www.gravatar.com/avatar/9d7a2fcd3b902c71412b196c29f5ba95?d=identicon&f=y&s=64" width="64" height="64"> Littlefinger | Premier | 16.0 | 15.8 | 44.7 | 17.8 | 16000 |
| <img src="https://www.gravatar.com/avatar/76fdf124f5765d774886a793d5023f32?d=identicon&f=y&s=64" width="64" height="64"> Varys | Premier | 14.7 | 26.0 | 51.0 | 18.1 | 14000 |
| <img src="https://res.cloudinary.com/dfcgw5cr6/image/upload/w_64,h_64,c_fill/The_Oracle.gif" width="64" height="64"> The Oracle | Premier | 13.6 | — | — | 13.6 | 20000 |
| <img src="https://www.gravatar.com/avatar/39c6087277499978d0500bb0205419d1?d=identicon&f=y&s=64" width="64" height="64"> Ripley | Premier | 13.6 | — | — | 13.6 | 20000 |
| <img src="https://res.cloudinary.com/hdyiihba/image/upload/w_64,h_64,c_fill/The_Merovingian.png" width="64" height="64"> The Merovingian | Premier | 12.5 | — | — | 12.5 | 20000 |
| <img src="https://www.gravatar.com/avatar/f68b87e0e12c96cc8ec181aa48e4e9b5?d=identicon&f=y&s=64" width="64" height="64"> EvilStewie | Premier | 10.9 | — | — | 10.9 | 20000 |
| <img src="https://res.cloudinary.com/dfcgw5cr6/image/upload/w_64,h_64,c_fill/Deep_Thought.jpg" width="64" height="64"> Deep Thought | Championship | 9.1 | 16.7 | — | 9.8 | 22000 |
| <img src="https://res.cloudinary.com/rzifhdkf/image/upload/w_64,h_64,c_fill/HAL_9000.png" width="64" height="64"> HAL 9000 | Premier | 8.6 | 18.0 | — | 10.5 | 25000 |
| <img src="https://www.gravatar.com/avatar/4d0a927fbe8ecbf7e9d05deea69a694f?d=identicon&f=y&s=64" width="64" height="64"> Shwimp | Premier | 8.3 | 18.2 | — | 10.3 | 25000 |
| <img src="https://www.gravatar.com/avatar/b4eed5a89f11670e6c411cab8aa2b5a7?d=identicon&f=y&s=64" width="64" height="64"> Stewie | Championship | 5.2 | 11.2 | 33.1 | 12.9 | 22000 |
| <img src="https://www.gravatar.com/avatar/28c4ac8b8ecc3772ff3d22f9bf6c737a?d=identicon&f=y&s=64" width="64" height="64"> Peter Beter | Championship | 5.0 | 13.0 | — | 10.4 | 22000 |
| <img src="https://www.gravatar.com/avatar/d51be008f389672257bcaa7b722a3df8?d=identicon&f=y&s=64" width="64" height="64"> Peter Griffin | Championship | 4.7 | 11.5 | — | 10.6 | 22000 |
| <img src="https://www.gravatar.com/avatar/8eb6692d51ca57e7464df1cb61624c89?d=identicon&f=y&s=64" width="64" height="64"> Columbo | Championship | 4.2 | 10.8 | 26.9 | 11.4 | 22000 |
| <img src="https://res.cloudinary.com/hdyiihba/image/upload/w_64,h_64,c_fill/Sloane_Avery.png" width="64" height="64"> Sloane | Championship | — | 10.7 | — | 10.7 | 20000 |
| <img src="https://res.cloudinary.com/dfcgw5cr6/image/upload/w_64,h_64,c_fill/Cal_Culatid.jpg" width="64" height="64"> Cal Culatid | Championship | — | 10.2 | 31.9 | 13.2 | 22000 |
| <img src="https://www.gravatar.com/avatar/4fb845c67d91bcb3178498fc6fe1fedc?d=identicon&f=y&s=64" width="64" height="64"> Diego | Level 1 | — | 10.2 | 28.7 | 12.0 | 20000 |
| <img src="https://res.cloudinary.com/hdyiihba/image/upload/w_64,h_64,c_fill/Zara.png" width="64" height="64"> Zara | Level 1 | — | 9.9 | 27.0 | 15.9 | 20000 |
| <img src="https://res.cloudinary.com/hdyiihba/image/upload/w_64,h_64,c_fill/Eva_Longoria.png" width="64" height="64"> Eva | Championship | — | 9.2 | 29.0 | 19.1 | 22000 |
| <img src="https://res.cloudinary.com/hdyiihba/image/upload/w_64,h_64,c_fill/Nuke_LaLoosh.png" width="64" height="64"> Nuke LaLoosh | Level 1 | — | 8.2 | 29.8 | 23.4 | 27000 |
| <img src="https://res.cloudinary.com/dfcgw5cr6/image/upload/w_64,h_64,c_fill/Honest_Abe.jpg" width="64" height="64"> Honest Abe | Level 1 | — | 7.2 | 29.2 | 23.7 | 24000 |
| <img src="https://res.cloudinary.com/hdyiihba/image/upload/w_64,h_64,c_fill/Remy_Beasley.png" width="64" height="64"> Remy | Level 1 | — | 4.6 | 21.5 | 20.7 | 21000 |
| <img src="https://res.cloudinary.com/hdyiihba/image/upload/w_64,h_64,c_fill/Finn_Carter.png" width="64" height="64"> Finn | Level 1 | — | — | 16.5 | 16.5 | 20000 |
| <img src="https://www.gravatar.com/avatar/17ad55a9b8384777496330d23e59d520?d=identicon&f=y&s=64" width="64" height="64"> Rick Sanchez | Level 1 | — | — | 16.2 | 16.2 | 20000 |
| <img src="https://res.cloudinary.com/hdyiihba/image/upload/w_64,h_64,c_fill/Meg_Griffin.png" width="64" height="64"> Meg Griffin | Level 1 | — | — | 15.9 | 15.9 | 20000 |
| <img src="https://www.gravatar.com/avatar/64489c85dc2fe0787b85cd87214b3810?d=identicon&f=y&s=64" width="64" height="64"> Alice | Level 1 | — | — | 11.8 | 11.8 | 20000 |
| <img src="https://www.gravatar.com/avatar/9b2b78033ecf0401a2feab5b4ba7462e?d=identicon&f=y&s=64" width="64" height="64"> Bruno | Level 1 | — | — | 11.4 | 11.4 | 20000 |
| <img src="https://res.cloudinary.com/hdyiihba/image/upload/w_64,h_64,c_fill/Liar_Liar.png" width="64" height="64"> Liar², Pants on Fire | Level 1 | — | — | 3.9 | 3.9 | 20000 |
| <img src="https://res.cloudinary.com/hdyiihba/image/upload/w_64,h_64,c_fill/Topper.png" width="64" height="64"> Topper | Level 1 | — | — | 2.8 | 2.8 | 20000 |
| <img src="https://www.gravatar.com/avatar/6e1def9bfa26327930ba900d46f8c9b3?d=identicon&f=y&s=64" width="64" height="64"> Cleo | Level 1 | — | — | 1.6 | 1.6 | 20000 |

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
