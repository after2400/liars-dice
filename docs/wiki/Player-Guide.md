<!-- source: docs/wiki/Player-Guide.md — edit here, not in the wiki directly -->

Everything you need to write a bot and compete in the league.

> **Action required by 2026-10-05:** The v1 `algo()` interface (positional args) is deprecated. Migrate to the v2 `GameContext` interface before the Q4 2026 tournament Monday or your player will be dropped from the league. See [Migration Guide](#migrating-from-v1-to-v2) below.

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

    def algo(self, ctx) -> Bet | None:
        # ctx.hand, ctx.prior_bet, ctx.total_dice, ctx.bet_history,
        # ctx.outcomes, ctx.stats, ctx.tier, ctx.round_players
        ...
```

The PR is validated and auto-merged. Your player competes starting from the next scheduled run.

**Modifying your player:** open a PR that modifies your existing file. The workflow verifies authorship and auto-merges.

**Removing your player:** open a PR that deletes your file. Self-removals are auto-merged.

> **PR rules (enforced by CI):** Each PR must touch only files under `players/` and add or modify exactly one file.

**Display name collisions:** if two players share the same `name`, the engine automatically appends each player's GitHub username in parentheses — e.g. `Fred (zachaustin01)`. Parentheses are reserved for this suffix, which is why they're prohibited in your `name` attribute.

---

## Player API

### `algo` inputs (v2)

`algo(self, ctx)` receives a single `GameContext` object. All fields are always present — no opt-in needed.

| `ctx` field         | Type          | Description                                                                                                                 |
| ------------------- | ------------- | --------------------------------------------------------------------------------------------------------------------------- |
| `ctx.hand`          | `list[int]`   | Your current dice (values 1–6). Mutable copy — changes stay local.                                                          |
| `ctx.prior_bet`     | `Bet \| None` | The last bid placed, or `None` if you are opening the round.                                                                |
| `ctx.total_dice`    | `int`         | Total dice in play across all active players.                                                                               |
| `ctx.bet_history`   | `list[dict]`  | Every accepted bid this game, oldest first. Entries are read-only.                                                          |
| `ctx.outcomes`      | `list[dict]`  | Revealed hands and results from all completed rounds. Entries are read-only. `outcome["hands"]["Alice"]` is a `tuple[int]`. |
| `ctx.stats`         | `GameStats`   | Pre-computed opponent statistics. Always a `GameStats` instance — never `None`.                                             |
| `ctx.tier`          | `str \| None` | The current league tier: `"L1"`, `"CH"`, or `"PRM"`. `None` during quarterly tournament pools.                              |
| `ctx.round_players` | `list[str]`   | Clockwise bid order for this round. `ctx.round_players[0]` is the opening bidder. Mutable copy.                             |

> **Performance note:** Use `ctx.stats` instead of scanning `bet_history` or `outcomes`. A full scan of `outcomes` at game 1000 iterates ~15,000 entries — done on every turn, that makes the last games ~2,000× slower than the first.

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

## Migrating from v1 to v2

The v1 interface used positional arguments:

```python
# v1 — deprecated, removed 2026-10-05
def algo(self, hand, prior_bet, total_dice, bet_history, outcomes, stats=None, tier=None, round_players=None):
    ...
```

The v2 interface uses a single `GameContext` object:

```python
# v2 — required after 2026-10-05
def algo(self, ctx):
    hand = ctx.hand
    prior_bet = ctx.prior_bet
    total_dice = ctx.total_dice
    bet_history = ctx.bet_history
    outcomes = ctx.outcomes
    stats = ctx.stats          # always GameStats, never None
    tier = ctx.tier
    round_players = ctx.round_players
```

**One breaking change:** `outcome["hands"]["PlayerName"]` is now a `tuple` instead of a `list`. Indexing (`hands["Alice"][0]`) and iteration (`for d in hands["Alice"]`) work unchanged. `.sort()` and `.append()` will raise `AttributeError` — use `sorted(hands["Alice"])` instead.

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
