# Liar's Dice League

A Python engine for running Liar's Dice games between algorithmic players. Players compete in a tiered league — submit a PR to join, and a daily scheduled run plays the games and updates standings.

## Current Standings

<!-- prettier-ignore-start -->
<!-- leaderboard-start -->
### Premier
| Player | Win% | Wins | Games |
|--------|------|------|-------|
| Diego  | 45.7 |  160 |   350 |
| Alice  | 28.2 |  127 |   450 |
| Finn   | 27.2 |   68 |   250 |
| Bruno  | 20.0 |   90 |   450 |

### Championship
| Player | Win% | Wins | Games |
|--------|------|------|-------|
| Cleo   |  1.1 |    5 |   450 |

### Level 1
*No players currently in Level 1.*

<!-- leaderboard-end -->
<!-- prettier-ignore-end -->

_Updated daily at 4am EST. Full history in the [season tracking issue](#)._

---

## How It Works

Two workflows replace the old per-PR game model:

**`register-player.yml`** — triggered when a PR touches `players/`

- Validates the player file (class name matches filename, display name ≤ 20 chars)
- Registers the player in `leaderboard.yaml` at the appropriate entry tier
- Commits the leaderboard update and auto-merges the PR
- No games run immediately

**`run-season.yml`** — runs daily at 4am EST (`0 9 * * *` UTC)

- Plays `N_GAMES` (default 250) games in each active tier, bottom-up: `inactive → L1 → CH → PRM`
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

**Promotion / relegation (per daily run):**

- Top player in each tier promotes to the tier above
- Bottom player(s) relegate to the tier below
- `times_inactive` increments each time a player is relegated to inactive

---

## Adding a Player

Open a PR that adds a single `.py` file to `players/`. The file must:

1. Be named after the class it contains — `fred.py` must define `class Fred`
2. Implement the `algo` method (see API below)
3. Optionally set a `name` attribute (display name, ≤ 20 chars, no parentheses)

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

The PR is validated and auto-merged. Your player competes starting from the next daily run.

**Modifying your player:** open a PR that modifies your existing file. The workflow verifies authorship (your `github_username` in the leaderboard must match the PR author) and auto-merges.

**Removing your player:** open a PR that deletes your file. Self-removals are auto-merged; admins can batch-delete multiple players.

---

## Player API

### `algo` inputs

| Parameter     | Type          | Description                                                 |
| ------------- | ------------- | ----------------------------------------------------------- |
| `hand`        | `list[int]`   | Your current dice (values 1–6)                              |
| `prior_bet`   | `Bet \| None` | The last bid placed, or `None` if you are opening the round |
| `total_dice`  | `int`         | Total dice in play across all active players                |
| `bet_history` | `list[dict]`  | Every accepted bid this game, oldest first                  |
| `outcomes`    | `list[dict]`  | Revealed hands and results from all completed rounds        |

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
uv run python -m game              # 1 game, all registered players
uv run python -m game 100 4        # 100 games, top 4 players
uv run python -m game 50 4 --tier PRM   # 50 games, PRM players only
```

Console shows one result line per game followed by a summary table. Full debug logs are written to `gamelog.log`.

---

## Project Structure

```
game/
  __main__.py          # entry point, logging, player selection, --tier filter
  components/
    script.py          # game loop and round orchestration
    bets.py            # Bet class, bet_validator, bet_grader
    series.py          # series runner and results formatter
    leaderboard.py     # leaderboard read/write, apply_season_results
    utils.py           # player loader

players/
  alice.py             # balanced strategy
  bruno.py             # aggressive strategy
  cleo.py              # cautious strategy
  diego.py             # hand-anchored strategy
  finn.py              # adaptive threshold strategy

.github/
  workflows/
    register-player.yml  # PR validation, registration, auto-merge
    run-season.yml       # daily scheduled season runner
    lint.yml             # ruff + commitlint on push/PR
  scripts/
    register_player.py   # validates player file, writes leaderboard entry
    run_season.py        # bottom-up tier runner, writes season summary
    lb_owner.py          # looks up github_username by class name
    lb_delete.py         # removes players from leaderboard by file path
    lb_update_name.py    # validates and updates display_name on modification

leaderboard.yaml         # source of truth — tier, stats, github_username per player
```
