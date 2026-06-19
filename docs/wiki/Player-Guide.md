<!-- source: docs/wiki/Player-Guide.md — edit here, not in the wiki directly -->

Everything you need to write a bot and compete in the league.

---

## Submitting a Player

If you don't have write access to the repo, fork it first: click **Fork** on GitHub, clone your fork, add your player file, then open a PR targeting `after2400/liars-dice:main`.

Open a PR that adds a single `.py` file to `players/`. The file must:

1. Be named after the class it contains — `fred.py` must define `class Fred`
2. Have a class name unique across the league — CI rejects duplicates (`Fred` already exists? try `Fred_<username>`)
3. Implement the `algo` method (see [Player API](#player-api) below)
4. Optionally set a `name` attribute (display name, ≤ 25 chars, no parentheses — see below)

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
        # optional — declare by name to opt in:
        # stats: GameStats | None = None
        # tier: str | None = None
        # round_players: list[str] | None = None
    ) -> Bet | None:
        ...
```

The PR is validated and auto-merged. Your player competes starting from the next scheduled run.

**Modifying your player:** open a PR that modifies your existing file. The workflow verifies authorship and auto-merges.

**Removing your player:** open a PR that deletes your file. Self-removals are auto-merged.

> **PR rules (enforced by CI):** Each PR must touch only files under `players/` and add or modify exactly one file.

**Display name collisions:** if two players share the same `name`, the engine automatically appends each player's GitHub username in parentheses — e.g. `Fred (zachaustin01)`. Parentheses are reserved for this suffix, which is why they're prohibited in your `name` attribute.

---

## Player API

### `algo` inputs

| Parameter       | Type                | Description                                                                                                                                                                                                                                          |
| --------------- | ------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `hand`          | `list[int]`         | Your current dice (values 1–6)                                                                                                                                                                                                                       |
| `prior_bet`     | `Bet \| None`       | The last bid placed, or `None` if you are opening the round                                                                                                                                                                                          |
| `total_dice`    | `int`               | Total dice in play across all active players                                                                                                                                                                                                         |
| `bet_history`   | `list[dict]`        | Every accepted bid this game, oldest first                                                                                                                                                                                                           |
| `outcomes`      | `list[dict]`        | Revealed hands and results from all completed rounds                                                                                                                                                                                                 |
| `stats`         | `GameStats \| None` | Pre-computed opponent statistics. Opt-in: declare `stats=None` in your signature. Use it instead of scanning `bet_history` or `outcomes` — those lists grow to tens of thousands of entries by game 1000.                                            |
| `tier`          | `str \| None`       | The current league tier: `"L1"`, `"CH"`, or `"PRM"`. Opt-in: declare `tier=None` in your signature. Receives `None` during quarterly tournament pools — **your `algo` must not crash when `tier` is `None`**.                                        |
| `round_players` | `list[str] \| None` | Clockwise bid order for this round. `round_players[0]` is always the opening bidder. The list shrinks as players are eliminated — it reflects only the active players for the current round. Opt-in: declare `round_players=None` in your signature. |

All opt-in parameters (`stats`, `tier`, `round_players`) are fully independent — declare any combination in any order.

> **Performance note:** If your strategy reads `bet_history` or `outcomes`, declare `stats=None` in your signature and use `GameStats` instead. A full scan of `outcomes` at game 1000 iterates ~15,000 entries — done on every turn, that makes the last games ~2,000× slower than the first.

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
{"game": int, "round": int, "player": str, "bet": Bet, "dice_count": int}
```

`dice_count` is the bidder's die count at the moment they placed that bid.

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

## Testing Locally

Drop your `.py` file in `players/` and run against the full field:

```bash
uv run python -m game 1000 --no-game-results
```

`--no-game-results` suppresses per-game lines and shows only the final summary table. Full debug logs go to `gamelog.log`.

**Validate before submitting:**

```bash
uv run python -m game.validate players/fred.py
```

Exits 0 if clean; exits 1 with an error message otherwise. The same check runs in CI when you open a PR.

### Simulating a season

To see how your bot performs over a full simulated quarter (tournament seeding + all regular Mondays), you'll need [`just`](https://just.systems/) installed (`brew install just` / `cargo install just`).

**1. Register locally** — adds your bot to the leaderboard for simulation:

```bash
just register-player players/fred.py your-github-username
```

> **Naming rule:** the class inside the file must match the filename exactly — `fred.py` must define `class Fred`.

**2. Simulate** — pick a scope:

```bash
just simulate-tournament           # one-off quarterly tournament
just simulate-season 2026-07-13    # one regular Monday season run
just simulate-quarter              # full quarter: tournament + all Mondays, writes sim-YYYY-QN.md
```

All simulation commands run with `DRY_RUN=1` — they modify `leaderboard.yaml` locally but make no GitHub API calls.

**3. Clean up afterward:**

```bash
just clean
```
