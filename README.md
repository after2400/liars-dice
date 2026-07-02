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
| <img src="https://www.gravatar.com/avatar/39c6087277499978d0500bb0205419d1?d=identicon&f=y&s=64" width="64" height="64"> Ripley | 18.8 | 528 | 25.3 | 1264 | 5000 |
| <img src="https://res.cloudinary.com/hdyiihba/image/upload/w_64,h_64,c_fill/The_Merovingian.png" width="64" height="64"> The Merovingian | 16.4 | 1135 | 24.2 | 1937 | 8000 |
| <img src="https://www.gravatar.com/avatar/30162ed78b6c10f731411f2fc440c24f?d=identicon&f=y&s=64" width="64" height="64"> The Oracle | 12.9 | 622 | 23.9 | 1435 | 6000 |
| <img src="https://www.gravatar.com/avatar/f68b87e0e12c96cc8ec181aa48e4e9b5?d=identicon&f=y&s=64" width="64" height="64"> EvilStewie | 12.5 | 2741 | 17.0 | 3062 | 18000 |
| <img src="https://www.gravatar.com/avatar/8cbd2c8774fa6b4be39342a10ea2f924?d=identicon&f=y&s=64" width="64" height="64"> Deep Thought | 12.0 | 2403 | 15.0 | 2403 | 16000 |
| <img src="https://www.gravatar.com/avatar/a9ac50f576aaa81628860c7808dee41c?d=identicon&f=y&s=64" width="64" height="64"> HAL 9000 | 9.6 | 185 | 25.3 | 1013 | 4000 |
| <img src="https://www.gravatar.com/avatar/b4eed5a89f11670e6c411cab8aa2b5a7?d=identicon&f=y&s=64" width="64" height="64"> Stewie | 7.3 | 4414 | 17.1 | 5463 | 32000 |
| <img src="https://www.gravatar.com/avatar/28c4ac8b8ecc3772ff3d22f9bf6c737a?d=identicon&f=y&s=64" width="64" height="64"> Peter Beter | 6.3 | 2433 | 14.3 | 2724 | 19000 |

### Championship
| Player | Season W% | Wins in CH | Win % Total | Total Wins | Games |
|--------|-----------|----------------|-------------|------------|-------|
| <img src="https://www.gravatar.com/avatar/d51be008f389672257bcaa7b722a3df8?d=identicon&f=y&s=64" width="64" height="64"> Peter Griffin | Relegated | 0 | 12.6 | 2397 | 19000 |
| <img src="https://www.gravatar.com/avatar/8eb6692d51ca57e7464df1cb61624c89?d=identicon&f=y&s=64" width="64" height="64"> Columbo | 13.9 | 1268 | 14.8 | 1777 | 12000 |
| <img src="https://res.cloudinary.com/hdyiihba/image/upload/w_64,h_64,c_fill/Sloane_Avery.png" width="64" height="64"> Sloane | 13.6 | 3817 | 17.0 | 7975 | 47000 |
| <img src="https://www.gravatar.com/avatar/c4bac00b500e30dc3f765f7cf9f16d13?d=identicon&f=y&s=64" width="64" height="64"> Cal Culatid | 13.0 | 2889 | 16.5 | 4453 | 27000 |
| <img src="https://www.gravatar.com/avatar/4fb845c67d91bcb3178498fc6fe1fedc?d=identicon&f=y&s=64" width="64" height="64"> Diego | 10.7 | 2922 | 16.8 | 6604 | 39350 |
| <img src="https://res.cloudinary.com/hdyiihba/image/upload/w_64,h_64,c_fill/Zara.png" width="64" height="64"> Zara | 9.9 | 4296 | 17.7 | 6711 | 38000 |
| <img src="https://res.cloudinary.com/hdyiihba/image/upload/w_64,h_64,c_fill/Eva_Longoria.png" width="64" height="64"> Eva | 9.7 | 5681 | 18.1 | 7059 | 39000 |
| <img src="https://res.cloudinary.com/hdyiihba/image/upload/w_64,h_64,c_fill/Nuke_LaLoosh.png" width="64" height="64"> Nuke LaLoosh | 7.9 | 714 | 15.3 | 4430 | 29000 |

### Level 1
| Player | Season W% | Wins in L1 | Win % Total | Total Wins | Games |
|--------|-----------|----------------|-------------|------------|-------|
| <img src="https://www.gravatar.com/avatar/630787985d20c3c7b8e004037b9637e0?d=identicon&f=y&s=64" width="64" height="64"> Honest Abe | Relegated | 920 | 14.3 | 3726 | 26000 |
| <img src="https://www.gravatar.com/avatar/17ad55a9b8384777496330d23e59d520?d=identicon&f=y&s=64" width="64" height="64"> Rick Sanchez | 27.0 | 3988 | 16.6 | 3988 | 24000 |
| <img src="https://res.cloudinary.com/hdyiihba/image/upload/w_64,h_64,c_fill/Finn_Carter.png" width="64" height="64"> Finn | 24.8 | 4354 | 16.8 | 7094 | 42250 |
| <img src="https://res.cloudinary.com/hdyiihba/image/upload/w_64,h_64,c_fill/Meg_Griffin.png" width="64" height="64"> Meg Griffin | 24.7 | 983 | 12.3 | 983 | 8000 |
| <img src="https://res.cloudinary.com/hdyiihba/image/upload/w_64,h_64,c_fill/Remy_Beasley.png" width="64" height="64"> Remy | 24.4 | 5037 | 17.2 | 8942 | 52000 |
| <img src="https://www.gravatar.com/avatar/64489c85dc2fe0787b85cd87214b3810?d=identicon&f=y&s=64" width="64" height="64"> Alice | 20.0 | 4816 | 15.8 | 5909 | 37450 |
| <img src="https://www.gravatar.com/avatar/9b2b78033ecf0401a2feab5b4ba7462e?d=identicon&f=y&s=64" width="64" height="64"> Bruno | 18.4 | 3709 | 12.8 | 4664 | 36450 |
| <img src="https://res.cloudinary.com/hdyiihba/image/upload/w_64,h_64,c_fill/Liar_Liar.png" width="64" height="64"> Liar², Pants on Fire | 7.7 | 1194 | 4.3 | 1194 | 28000 |
| <img src="https://www.gravatar.com/avatar/6e1def9bfa26327930ba900d46f8c9b3?d=identicon&f=y&s=64" width="64" height="64"> Cleo | 5.3 | 1781 | 4.8 | 1798 | 37450 |
| <img src="https://res.cloudinary.com/hdyiihba/image/upload/w_64,h_64,c_fill/Topper.png" width="64" height="64"> Topper | 3.0 | 2427 | 7.4 | 2427 | 33000 |

### Quarter Leaderboard

| Player | Tier | PRM W% | CH W% | L1 W% | Total W% | Games |
|--------|------|--------|-------|-------|----------|-------|
| <img src="https://res.cloudinary.com/hdyiihba/image/upload/w_64,h_64,c_fill/Zara.png" width="64" height="64"> Zara | Championship | 20.1 | 16.5 | — | 17.7 | 38000 |
| <img src="https://res.cloudinary.com/hdyiihba/image/upload/w_64,h_64,c_fill/The_Merovingian.png" width="64" height="64"> The Merovingian | Premier | 18.9 | 33.4 | 46.8 | 24.2 | 8000 |
| <img src="https://www.gravatar.com/avatar/4fb845c67d91bcb3178498fc6fe1fedc?d=identicon&f=y&s=64" width="64" height="64"> Diego | Championship | 18.1 | 15.4 | — | 16.8 | 39350 |
| <img src="https://www.gravatar.com/avatar/39c6087277499978d0500bb0205419d1?d=identicon&f=y&s=64" width="64" height="64"> Ripley | Premier | 17.6 | 26.1 | 47.5 | 25.3 | 5000 |
| <img src="https://res.cloudinary.com/hdyiihba/image/upload/w_64,h_64,c_fill/Eva_Longoria.png" width="64" height="64"> Eva | Championship | 17.2 | 18.3 | — | 18.1 | 39000 |
| <img src="https://www.gravatar.com/avatar/b4eed5a89f11670e6c411cab8aa2b5a7?d=identicon&f=y&s=64" width="64" height="64"> Stewie | Premier | 16.3 | 19.0 | 28.8 | 17.1 | 32000 |
| <img src="https://www.gravatar.com/avatar/f68b87e0e12c96cc8ec181aa48e4e9b5?d=identicon&f=y&s=64" width="64" height="64"> EvilStewie | Premier | 16.1 | 32.1 | — | 17.0 | 18000 |
| <img src="https://www.gravatar.com/avatar/30162ed78b6c10f731411f2fc440c24f?d=identicon&f=y&s=64" width="64" height="64"> The Oracle | Premier | 15.6 | 36.9 | 44.4 | 23.9 | 6000 |
| <img src="https://www.gravatar.com/avatar/8cbd2c8774fa6b4be39342a10ea2f924?d=identicon&f=y&s=64" width="64" height="64"> Deep Thought | Premier | 15.0 | — | — | 15.0 | 16000 |
| <img src="https://www.gravatar.com/avatar/64489c85dc2fe0787b85cd87214b3810?d=identicon&f=y&s=64" width="64" height="64"> Alice | Level 1 | 14.8 | 12.6 | 16.6 | 15.8 | 37450 |
| <img src="https://res.cloudinary.com/hdyiihba/image/upload/w_64,h_64,c_fill/Finn_Carter.png" width="64" height="64"> Finn | Level 1 | 14.0 | 12.7 | 20.7 | 16.8 | 42250 |
| <img src="https://res.cloudinary.com/hdyiihba/image/upload/w_64,h_64,c_fill/Sloane_Avery.png" width="64" height="64"> Sloane | Championship | 13.9 | 22.5 | — | 17.0 | 47000 |
| <img src="https://www.gravatar.com/avatar/28c4ac8b8ecc3772ff3d22f9bf6c737a?d=identicon&f=y&s=64" width="64" height="64"> Peter Beter | Premier | 13.5 | 29.1 | — | 14.3 | 19000 |
| <img src="https://res.cloudinary.com/hdyiihba/image/upload/w_64,h_64,c_fill/Nuke_LaLoosh.png" width="64" height="64"> Nuke LaLoosh | Championship | 13.3 | 17.8 | 52.1 | 15.3 | 29000 |
| <img src="https://www.gravatar.com/avatar/c4bac00b500e30dc3f765f7cf9f16d13?d=identicon&f=y&s=64" width="64" height="64"> Cal Culatid | Championship | 12.8 | 16.1 | 26.5 | 16.5 | 27000 |
| <img src="https://www.gravatar.com/avatar/d51be008f389672257bcaa7b722a3df8?d=identicon&f=y&s=64" width="64" height="64"> Peter Griffin | Championship | 12.6 | — | — | 12.6 | 19000 |
| <img src="https://www.gravatar.com/avatar/9b2b78033ecf0401a2feab5b4ba7462e?d=identicon&f=y&s=64" width="64" height="64"> Bruno | Level 1 | 10.9 | 13.8 | 12.8 | 12.8 | 36450 |
| <img src="https://res.cloudinary.com/hdyiihba/image/upload/w_64,h_64,c_fill/Remy_Beasley.png" width="64" height="64"> Remy | Level 1 | 10.6 | 13.2 | 22.9 | 17.2 | 52000 |
| <img src="https://www.gravatar.com/avatar/a9ac50f576aaa81628860c7808dee41c?d=identicon&f=y&s=64" width="64" height="64"> HAL 9000 | Premier | 9.2 | 22.2 | 60.6 | 25.3 | 4000 |
| <img src="https://www.gravatar.com/avatar/8eb6692d51ca57e7464df1cb61624c89?d=identicon&f=y&s=64" width="64" height="64"> Columbo | Championship | 7.2 | 15.8 | 29.3 | 14.8 | 12000 |
| <img src="https://www.gravatar.com/avatar/6e1def9bfa26327930ba900d46f8c9b3?d=identicon&f=y&s=64" width="64" height="64"> Cleo | Level 1 | 1.1 | 0.3 | 5.4 | 4.8 | 37450 |
| <img src="https://www.gravatar.com/avatar/630787985d20c3c7b8e004037b9637e0?d=identicon&f=y&s=64" width="64" height="64"> Honest Abe | Level 1 | — | 12.2 | 30.7 | 14.3 | 26000 |
| <img src="https://www.gravatar.com/avatar/17ad55a9b8384777496330d23e59d520?d=identicon&f=y&s=64" width="64" height="64"> Rick Sanchez | Level 1 | — | — | 16.6 | 16.6 | 24000 |
| <img src="https://res.cloudinary.com/hdyiihba/image/upload/w_64,h_64,c_fill/Meg_Griffin.png" width="64" height="64"> Meg Griffin | Level 1 | — | — | 12.3 | 12.3 | 8000 |
| <img src="https://res.cloudinary.com/hdyiihba/image/upload/w_64,h_64,c_fill/Topper.png" width="64" height="64"> Topper | Level 1 | — | — | 7.4 | 7.4 | 33000 |
| <img src="https://res.cloudinary.com/hdyiihba/image/upload/w_64,h_64,c_fill/Liar_Liar.png" width="64" height="64"> Liar², Pants on Fire | Level 1 | — | — | 4.3 | 4.3 | 28000 |

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
