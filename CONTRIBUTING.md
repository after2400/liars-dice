# Contributing

## Adding a Player

Open a PR that adds a single `.py` file to `players/`. The file must:

1. Be named after the class it contains — `fred.py` must define `class Fred`
2. Implement the `algo` method (see [Player API](#player-api) below)
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

## Running Locally

Requires [`uv`](https://docs.astral.sh/uv/) and [`just`](https://just.systems/).

```bash
# one-time dev setup
just develop
```

### Tests and linting

```bash
just pytest   # full test suite
just lint     # ruff check + format check
```

### Simulating runs

```bash
just simulate-season               # dry run with today's date
just simulate-season 2026-07-07    # dry run with a specific date
just simulate-tournament           # dry run the next quarterly tournament
just clean                         # reset leaderboard.yaml and season_summary.md afterward
```

### Running games directly

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
