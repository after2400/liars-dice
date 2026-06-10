# Liar's Dice League

A Python engine for running Liar's Dice games between algorithmic players. Players compete in a tiered league — submit a PR to join, and a weekly scheduled run plays the games and updates standings (extra runs trigger automatically when a player file changes).

## Current Standings

<!-- prettier-ignore-start -->
<!-- leaderboard-start -->
### Premier
| Player | Win % in PRM | Wins in PRM | Win % Total | Total Wins | Games |
|--------|----------------|----------------|-------------|------------|-------|
| Diego | 29.0 | 972 | 29.0 | 972 | 3350 |
| Zara | 27.2 | 817 | 28.5 | 1141 | 3000 |
| Sloane | 26.1 | 522 | 28.5 | 1140 | 2000 |
| Eva | 19.8 | 198 | 31.4 | 1255 | 1000 |

### Championship
| Player | Win % in CH | Wins in CH | Win % Total | Total Wins | Games |
|--------|----------------|----------------|-------------|------------|-------|
| Remy | 20.1 | 604 | 20.1 | 604 | 3000 |
| Bruno | 15.2 | 152 | 12.1 | 419 | 1000 |
| Alice | 12.2 | 243 | 13.2 | 457 | 2000 |
| Finn | 0.0 | 0 | 14.0 | 455 | 0 |

### Level 1
| Player | Win % in L1 | Wins in L1 | Win % Total | Total Wins | Games |
|--------|----------------|----------------|-------------|------------|-------|
| Cleo | 0.0 | 0 | 0.3 | 7 | 0 |

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

## Adding a Player

Open a PR that adds a single `.py` file to `players/`. The file must:

1. Be named after the class it contains — `fred.py` must define `class Fred`
2. Implement the `algo` method (see API below)
3. Optionally set a `name` attribute (display name, ≤ 25 chars, no parentheses)

```python
from game.components.bets import Bet

class Fred:
    name = "Fred the Magnificent"  # optional — defaults to class name

    def algo(
        self,
        hand: list[int],
        prior_bet: Bet | None,
        total_dice: int,
        bet_history: list[dict],
        outcomes: list[dict],
    ) -> Bet | None:
        ...
```

The PR is validated and auto-merged. Your player competes starting from the next scheduled run.

**Modifying your player:** open a PR that modifies your existing file. The workflow verifies authorship (your `github_username` in the leaderboard must match the PR author) and auto-merges.

**Removing your player:** open a PR that deletes your file. Self-removals are auto-merged; admins can batch-delete multiple players.

---

## Player API

### `algo` inputs

| Parameter     | Type                | Description                                                                                                                                                                                                                                                                                                                        |
| ------------- | ------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `hand`        | `list[int]`         | Your current dice (values 1–6)                                                                                                                                                                                                                                                                                                     |
| `prior_bet`   | `Bet \| None`       | The last bid placed, or `None` if you are opening the round                                                                                                                                                                                                                                                                        |
| `total_dice`  | `int`               | Total dice in play across all active players                                                                                                                                                                                                                                                                                       |
| `bet_history` | `list[dict]`        | Every accepted bid this game, oldest first                                                                                                                                                                                                                                                                                         |
| `outcomes`    | `list[dict]`        | Revealed hands and results from all completed rounds                                                                                                                                                                                                                                                                               |
| `stats`       | `GameStats \| None` | Pre-computed opponent statistics. Present only if your `algo` declares a 6th parameter. Use it instead of scanning `bet_history` or `outcomes` — those lists grow to tens of thousands of entries by game 1000 and scanning them on every turn makes your player slow. See `game/components/stats.py` for the full attribute list. |

> **Performance note:** If your strategy reads `bet_history` or `outcomes`, declare `stats=None`
> as a 6th parameter and use `GameStats` instead. A full scan of `outcomes` at game 1000
> iterates ~15,000 entries — done on every turn, that makes the last games ~2,000× slower
> than the first.

### Return value

- Return a `Bet(quantity, face, self.name)` to place a bid.
- Return `None` to call liar. _(Not allowed on the opening bid — you'll be penalised.)_

Returning an invalid bid (doesn't raise the prior bet, or bids 1s after a non-1 opening) is penalised — you lose a die automatically.

### `Bet`

```python
Bet(quantity: int, face: int, player: str)

bet.quantity  # int — claimed number of matching dice
bet.face      # int — claimed face value (1–6)
bet.player    # str — name of the player who placed it
```

### `bet_history` entries

```python
{"game": int, "round": int, "player": str, "bet": Bet}
```

### `outcomes` entries

```python
{
    "game":        int,   # game number in the series
    "round":       int,   # round number
    "hands":       dict,  # {player_name: [dice]} for all active players
    "final_bet":   Bet,   # the bid that was challenged
    "bidder":      str,   # who placed the final bet
    "challenger":  str,   # who called liar
    "bet_held":    bool,  # True if the bid held up
    "loser":       str,   # who lost a die
}
```

---

## Rules

Each player starts with **5 dice**. Each round:

1. All active players roll their dice in secret.
2. Starting from a random player, players take turns bidding — claiming there are at least _N_ dice showing face _F_ across all hands combined.
3. Each bid must raise the previous one: increase the quantity, or keep the quantity and increase the face value.
4. Instead of bidding, any player may call **liar** on the previous bid.
5. All dice are revealed. If the bid holds (total matching dice ≥ claimed quantity), the challenger loses a die. If it fails, the bidder loses a die.
6. The winner of each challenge leads the next round.
7. A player is eliminated when their dice reach 0. Last player standing wins.

### 1s as wilds

**1s count as wild** — they satisfy any non-1 bid. If the opening bid of a round is on face 1:

- 1s are **not** wild for that round (counted literally only).
- Subsequent bids on 1s are not allowed if the round opened on any other face.

---

## Running Locally

```bash
uv run python -m game [N_GAMES] [TOP_N] [--tier TIER]
```

Examples:

```bash
uv run python -m game              # 1 game, every player file in players/
uv run python -m game 100 4        # 100 games, all players
uv run python -m game 50 4 --tier PRM   # 50 games, PRM players only
```

**Testing a new player before submitting a PR:** drop your `.py` file in `players/` and run without `--tier`. Every file in the directory is included regardless of leaderboard status, so your player competes immediately against the full field:

```bash
uv run python -m game 1000 --no-game-results
```

`--no-game-results` suppresses the per-game lines and shows only the final summary table. Full debug logs are written to `gamelog.log`.

**Validating a player file before submitting:**

```bash
uv run python -m game.validate players/fred.py
```

Exits 0 if the file imports and instantiates cleanly; exits 1 with an error message otherwise. The same check runs automatically in CI when you open a PR.

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
    lint.yml             # ruff + commitlint on push/PR
  scripts/
    register_player.py   # validates player file, writes leaderboard entry
    run_season.py        # bottom-up tier runner, writes season summary
    lb_owner.py          # looks up github_username by class name
    lb_delete.py         # removes players from leaderboard by file path
    lb_update_name.py    # validates and updates display_name on modification

leaderboard.yaml         # source of truth — tier, stats, github_username per player
```
