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
| <img src="https://www.gravatar.com/avatar/9d7a2fcd3b902c71412b196c29f5ba95?d=identicon&f=y&s=64" width="64" height="64"> Littlefinger | 18.3 | 2598 | 17.8 | 3203 | 18000 |
| <img src="https://www.gravatar.com/avatar/76fdf124f5765d774886a793d5023f32?d=identicon&f=y&s=64" width="64" height="64"> Varys | 15.5 | 2061 | 17.7 | 2831 | 16000 |
| <img src="https://res.cloudinary.com/dfcgw5cr6/image/upload/w_64,h_64,c_fill/The_Oracle.gif" width="64" height="64"> The Oracle | 12.9 | 2990 | 13.6 | 2990 | 22000 |
| <img src="https://res.cloudinary.com/hdyiihba/image/upload/w_64,h_64,c_fill/The_Merovingian.png" width="64" height="64"> The Merovingian | 11.7 | 2710 | 12.3 | 2710 | 22000 |
| <img src="https://www.gravatar.com/avatar/39c6087277499978d0500bb0205419d1?d=identicon&f=y&s=64" width="64" height="64"> Ripley | 11.2 | 2960 | 13.5 | 2960 | 22000 |
| <img src="https://res.cloudinary.com/rzifhdkf/image/upload/w_64,h_64,c_fill/HAL_9000.png" width="64" height="64"> HAL 9000 | 7.7 | 1865 | 10.5 | 2952 | 28000 |
| <img src="https://www.gravatar.com/avatar/f68b87e0e12c96cc8ec181aa48e4e9b5?d=identicon&f=y&s=64" width="64" height="64"> EvilStewie | 7.6 | 2355 | 10.7 | 2355 | 22000 |
| <img src="https://www.gravatar.com/avatar/4d0a927fbe8ecbf7e9d05deea69a694f?d=identicon&f=y&s=64" width="64" height="64"> Shwimp | 7.6 | 1836 | 10.2 | 2747 | 27000 |

### Championship
| Player | Season W% | Wins in CH | Win % Total | Total Wins | Games |
|--------|-----------|----------------|-------------|------------|-------|
| <img src="https://res.cloudinary.com/dfcgw5cr6/image/upload/w_64,h_64,c_fill/Deep_Thought.jpg" width="64" height="64"> Deep Thought | Relegated | 512 | 9.9 | 2467 | 25000 |
| <img src="https://www.gravatar.com/avatar/28c4ac8b8ecc3772ff3d22f9bf6c737a?d=identicon&f=y&s=64" width="64" height="64"> Peter Beter | 12.7 | 2185 | 10.6 | 2535 | 24000 |
| <img src="https://www.gravatar.com/avatar/8eb6692d51ca57e7464df1cb61624c89?d=identicon&f=y&s=64" width="64" height="64"> Columbo | 11.6 | 2049 | 11.3 | 2714 | 24000 |
| <img src="https://www.gravatar.com/avatar/d51be008f389672257bcaa7b722a3df8?d=identicon&f=y&s=64" width="64" height="64"> Peter Griffin | 11.3 | 2424 | 10.7 | 2565 | 24000 |
| <img src="https://res.cloudinary.com/hdyiihba/image/upload/w_64,h_64,c_fill/Sloane_Avery.png" width="64" height="64"> Sloane | 10.7 | 2371 | 10.8 | 2371 | 22000 |
| <img src="https://www.gravatar.com/avatar/b4eed5a89f11670e6c411cab8aa2b5a7?d=identicon&f=y&s=64" width="64" height="64"> Stewie | 10.1 | 2349 | 12.8 | 3062 | 24000 |
| <img src="https://res.cloudinary.com/hdyiihba/image/upload/w_64,h_64,c_fill/Eva_Longoria.png" width="64" height="64"> Eva | 9.1 | 1180 | 18.2 | 4369 | 24000 |
| <img src="https://res.cloudinary.com/dfcgw5cr6/image/upload/w_64,h_64,c_fill/Cal_Culatid.jpg" width="64" height="64"> Cal Culatid | 8.4 | 2120 | 12.8 | 3077 | 24000 |

### Level 1
| Player | Season W% | Wins in L1 | Win % Total | Total Wins | Games |
|--------|-----------|----------------|-------------|------------|-------|
| <img src="https://res.cloudinary.com/hdyiihba/image/upload/w_64,h_64,c_fill/Zara.png" width="64" height="64"> Zara | Relegated | 2510 | 16.8 | 3872 | 23000 |
| <img src="https://www.gravatar.com/avatar/4fb845c67d91bcb3178498fc6fe1fedc?d=identicon&f=y&s=64" width="64" height="64"> Diego | 29.8 | 1150 | 13.5 | 2978 | 22000 |
| <img src="https://res.cloudinary.com/hdyiihba/image/upload/w_64,h_64,c_fill/Nuke_LaLoosh.png" width="64" height="64"> Nuke LaLoosh | 26.0 | 6243 | 23.2 | 6967 | 30000 |
| <img src="https://res.cloudinary.com/dfcgw5cr6/image/upload/w_64,h_64,c_fill/Honest_Abe.jpg" width="64" height="64"> Honest Abe | 23.6 | 5747 | 23.8 | 6181 | 26000 |
| <img src="https://res.cloudinary.com/hdyiihba/image/upload/w_64,h_64,c_fill/Remy_Beasley.png" width="64" height="64"> Remy | 18.5 | 4657 | 20.4 | 4703 | 23000 |
| <img src="https://res.cloudinary.com/hdyiihba/image/upload/w_64,h_64,c_fill/Finn_Carter.png" width="64" height="64"> Finn | 15.7 | 3628 | 16.5 | 3628 | 22000 |
| <img src="https://www.gravatar.com/avatar/17ad55a9b8384777496330d23e59d520?d=identicon&f=y&s=64" width="64" height="64"> Rick Sanchez | 14.0 | 3500 | 15.9 | 3500 | 22000 |
| <img src="https://www.gravatar.com/avatar/9b2b78033ecf0401a2feab5b4ba7462e?d=identicon&f=y&s=64" width="64" height="64"> Bruno | 13.3 | 2547 | 11.6 | 2547 | 22000 |
| <img src="https://res.cloudinary.com/hdyiihba/image/upload/w_64,h_64,c_fill/Meg_Griffin.png" width="64" height="64"> Meg Griffin | 11.0 | 3401 | 15.5 | 3401 | 22000 |
| <img src="https://www.gravatar.com/avatar/64489c85dc2fe0787b85cd87214b3810?d=identicon&f=y&s=64" width="64" height="64"> Alice | 9.6 | 2557 | 11.6 | 2557 | 22000 |
| <img src="https://res.cloudinary.com/hdyiihba/image/upload/w_64,h_64,c_fill/Liar_Liar.png" width="64" height="64"> Liar², Pants on Fire | 3.6 | 840 | 3.8 | 840 | 22000 |
| <img src="https://res.cloudinary.com/hdyiihba/image/upload/w_64,h_64,c_fill/Topper.png" width="64" height="64"> Topper | 1.4 | 583 | 2.6 | 583 | 22000 |
| <img src="https://www.gravatar.com/avatar/6e1def9bfa26327930ba900d46f8c9b3?d=identicon&f=y&s=64" width="64" height="64"> Cleo | 1.0 | 335 | 1.5 | 335 | 22000 |

### Quarter Leaderboard

| Player | Tier | PRM W% | CH W% | L1 W% | Total W% | Games |
|--------|------|--------|-------|-------|----------|-------|
| <img src="https://www.gravatar.com/avatar/9d7a2fcd3b902c71412b196c29f5ba95?d=identicon&f=y&s=64" width="64" height="64"> Littlefinger | Premier | 16.2 | 15.8 | 44.7 | 17.8 | 18000 |
| <img src="https://www.gravatar.com/avatar/76fdf124f5765d774886a793d5023f32?d=identicon&f=y&s=64" width="64" height="64"> Varys | Premier | 14.7 | 26.0 | 51.0 | 17.7 | 16000 |
| <img src="https://res.cloudinary.com/dfcgw5cr6/image/upload/w_64,h_64,c_fill/The_Oracle.gif" width="64" height="64"> The Oracle | Premier | 13.6 | — | — | 13.6 | 22000 |
| <img src="https://www.gravatar.com/avatar/39c6087277499978d0500bb0205419d1?d=identicon&f=y&s=64" width="64" height="64"> Ripley | Premier | 13.5 | — | — | 13.5 | 22000 |
| <img src="https://res.cloudinary.com/hdyiihba/image/upload/w_64,h_64,c_fill/The_Merovingian.png" width="64" height="64"> The Merovingian | Premier | 12.3 | — | — | 12.3 | 22000 |
| <img src="https://www.gravatar.com/avatar/f68b87e0e12c96cc8ec181aa48e4e9b5?d=identicon&f=y&s=64" width="64" height="64"> EvilStewie | Premier | 10.7 | — | — | 10.7 | 22000 |
| <img src="https://res.cloudinary.com/dfcgw5cr6/image/upload/w_64,h_64,c_fill/Deep_Thought.jpg" width="64" height="64"> Deep Thought | Championship | 8.9 | 17.1 | — | 9.9 | 25000 |
| <img src="https://res.cloudinary.com/rzifhdkf/image/upload/w_64,h_64,c_fill/HAL_9000.png" width="64" height="64"> HAL 9000 | Premier | 8.5 | 18.1 | — | 10.5 | 28000 |
| <img src="https://www.gravatar.com/avatar/4d0a927fbe8ecbf7e9d05deea69a694f?d=identicon&f=y&s=64" width="64" height="64"> Shwimp | Premier | 8.3 | 18.2 | — | 10.2 | 27000 |
| <img src="https://www.gravatar.com/avatar/b4eed5a89f11670e6c411cab8aa2b5a7?d=identicon&f=y&s=64" width="64" height="64"> Stewie | Championship | 5.2 | 11.2 | 33.1 | 12.8 | 24000 |
| <img src="https://www.gravatar.com/avatar/28c4ac8b8ecc3772ff3d22f9bf6c737a?d=identicon&f=y&s=64" width="64" height="64"> Peter Beter | Championship | 5.0 | 12.9 | — | 10.6 | 24000 |
| <img src="https://www.gravatar.com/avatar/d51be008f389672257bcaa7b722a3df8?d=identicon&f=y&s=64" width="64" height="64"> Peter Griffin | Championship | 4.7 | 11.5 | — | 10.7 | 24000 |
| <img src="https://www.gravatar.com/avatar/8eb6692d51ca57e7464df1cb61624c89?d=identicon&f=y&s=64" width="64" height="64"> Columbo | Championship | 4.2 | 10.8 | 26.9 | 11.3 | 24000 |
| <img src="https://res.cloudinary.com/hdyiihba/image/upload/w_64,h_64,c_fill/Sloane_Avery.png" width="64" height="64"> Sloane | Championship | — | 10.8 | — | 10.8 | 22000 |
| <img src="https://www.gravatar.com/avatar/4fb845c67d91bcb3178498fc6fe1fedc?d=identicon&f=y&s=64" width="64" height="64"> Diego | Level 1 | — | 10.2 | 28.7 | 13.5 | 22000 |
| <img src="https://res.cloudinary.com/dfcgw5cr6/image/upload/w_64,h_64,c_fill/Cal_Culatid.jpg" width="64" height="64"> Cal Culatid | Championship | — | 10.1 | 31.9 | 12.8 | 24000 |
| <img src="https://res.cloudinary.com/hdyiihba/image/upload/w_64,h_64,c_fill/Zara.png" width="64" height="64"> Zara | Level 1 | — | 9.7 | 27.9 | 16.8 | 23000 |
| <img src="https://res.cloudinary.com/hdyiihba/image/upload/w_64,h_64,c_fill/Eva_Longoria.png" width="64" height="64"> Eva | Championship | — | 9.1 | 29.0 | 18.2 | 24000 |
| <img src="https://res.cloudinary.com/hdyiihba/image/upload/w_64,h_64,c_fill/Nuke_LaLoosh.png" width="64" height="64"> Nuke LaLoosh | Level 1 | — | 8.0 | 29.7 | 23.2 | 30000 |
| <img src="https://res.cloudinary.com/dfcgw5cr6/image/upload/w_64,h_64,c_fill/Honest_Abe.jpg" width="64" height="64"> Honest Abe | Level 1 | — | 7.2 | 28.7 | 23.8 | 26000 |
| <img src="https://res.cloudinary.com/hdyiihba/image/upload/w_64,h_64,c_fill/Remy_Beasley.png" width="64" height="64"> Remy | Level 1 | — | 4.6 | 21.2 | 20.4 | 23000 |
| <img src="https://res.cloudinary.com/hdyiihba/image/upload/w_64,h_64,c_fill/Finn_Carter.png" width="64" height="64"> Finn | Level 1 | — | — | 16.5 | 16.5 | 22000 |
| <img src="https://www.gravatar.com/avatar/17ad55a9b8384777496330d23e59d520?d=identicon&f=y&s=64" width="64" height="64"> Rick Sanchez | Level 1 | — | — | 15.9 | 15.9 | 22000 |
| <img src="https://res.cloudinary.com/hdyiihba/image/upload/w_64,h_64,c_fill/Meg_Griffin.png" width="64" height="64"> Meg Griffin | Level 1 | — | — | 15.5 | 15.5 | 22000 |
| <img src="https://www.gravatar.com/avatar/64489c85dc2fe0787b85cd87214b3810?d=identicon&f=y&s=64" width="64" height="64"> Alice | Level 1 | — | — | 11.6 | 11.6 | 22000 |
| <img src="https://www.gravatar.com/avatar/9b2b78033ecf0401a2feab5b4ba7462e?d=identicon&f=y&s=64" width="64" height="64"> Bruno | Level 1 | — | — | 11.6 | 11.6 | 22000 |
| <img src="https://res.cloudinary.com/hdyiihba/image/upload/w_64,h_64,c_fill/Liar_Liar.png" width="64" height="64"> Liar², Pants on Fire | Level 1 | — | — | 3.8 | 3.8 | 22000 |
| <img src="https://res.cloudinary.com/hdyiihba/image/upload/w_64,h_64,c_fill/Topper.png" width="64" height="64"> Topper | Level 1 | — | — | 2.6 | 2.6 | 22000 |
| <img src="https://www.gravatar.com/avatar/6e1def9bfa26327930ba900d46f8c9b3?d=identicon&f=y&s=64" width="64" height="64"> Cleo | Level 1 | — | — | 1.5 | 1.5 | 22000 |

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
