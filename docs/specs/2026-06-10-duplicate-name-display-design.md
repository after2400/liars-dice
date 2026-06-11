# Duplicate Player Name Display — Design

## Goal

When two or more registered players share the same `display_name`, disambiguate
them in all rendered output by appending a unique suffix. When a name is unique
(the normal case), render it bare exactly as today. This makes the leaderboard,
standings, season summary, and movement messages unambiguous without changing
how unique names look.

## Background

The leaderboard is keyed by **class name** (unique, immutable, must match the
player's filename). `display_name` and `github_username` are stored as separate
fields. Display names are _not_ uniqueness-constrained, so two authors can each
ship a player named "Topper" (as different classes). Today every renderer shows
`display_name` alone (falling back to the class name), so two "Topper"s would
render identically.

The `"{display_name} ({github_username})"` render format was described in the
scheduled-league spec but never implemented. This design implements it
**conditionally** — only on collision.

Note: the rule that forbids parentheses in a `display_name` (so a user-supplied
name can't be confused with this suffix) lives on the separate
`chore/name-limit-25` branch. This feature does not depend on that branch to
function; the two are thematically paired but independently shippable.

## The Rule

A player's render string is its `display_name`, **unless** 2+ players across the
entire leaderboard share that `display_name`. On collision, append a suffix:

- Use ` (github_username)` when the username is non-empty **and** unique within
  the colliding group.
- Otherwise fall back to ` (class_name)`, which is always unique (it's the
  leaderboard key).

This single rule covers every case unambiguously:

| Colliding "Topper" group | Suffixes                   | Reason                                             |
| ------------------------ | -------------------------- | -------------------------------------------------- |
| `after2400`, `jschmoe`   | `(after2400)`, `(jschmoe)` | usernames unique → use them                        |
| `after2400`, `''`        | `(after2400)`, `(<class>)` | empty username → class fallback                    |
| `''`, `''`               | `(<classA>)`, `(<classB>)` | neither unique → class for both                    |
| `after2400`, `after2400` | `(<classA>)`, `(<classB>)` | same author → username not unique → class for both |

**Scope is global**: collision is detected across the whole `players` dict (all
tiers including inactive), so a player renders identically in every table and
message.

## Components

### `build_display_names(players: dict) -> dict[str, str]`

New pure function in `game/components/leaderboard.py`. Maps each class name (the
leaderboard key) to its render string per the rule above. Built once per render
pass; callers look up by class name.

```python
from collections import Counter, defaultdict

def build_display_names(players: dict) -> dict[str, str]:
    names = {cn: p.get("display_name", cn) for cn, p in players.items()}
    name_counts = Counter(names.values())

    groups: dict[str, list[str]] = defaultdict(list)
    for cn, name in names.items():
        groups[name].append(cn)

    result: dict[str, str] = {}
    for cn, name in names.items():
        if name_counts[name] <= 1:
            result[cn] = name
            continue
        username = players[cn].get("github_username") or ""
        username_unique = bool(username) and sum(
            (players[s].get("github_username") or "") == username for s in groups[name]
        ) == 1
        result[cn] = f"{name} ({username if username_unique else cn})"
    return result
```

### Call sites (5)

All current renders use `p.get("display_name", <class_name>)`; each switches to a
lookup in a map built once from the full players dict.

| File                             | Site                                 | Current   |
| -------------------------------- | ------------------------------------ | --------- |
| `game/components/leaderboard.py` | `apply_season_results._display()`    | line ~182 |
| `.github/scripts/run_season.py`  | inactive players list                | line ~175 |
| `.github/scripts/run_season.py`  | game-results table                   | line ~202 |
| `.github/scripts/run_season.py`  | promotion/relegation movements       | line ~214 |
| `.github/scripts/run_season.py`  | standings table (`_standings_table`) | line ~251 |

`run_season.py` already puts repo root on `sys.path`, so it imports
`build_display_names` from `game.components.leaderboard`. The summary builder
constructs the `display_names` map once from the full `players` dict and passes
it into `_standings_table(tier_players, tier, display_names)` as a new
parameter, so the table resolves each row by class name.

## Data Flow

1. A render pass has the full `players` dict (run_season: `players`;
   leaderboard: `data["players"]`).
2. `display_names = build_display_names(players)` once.
3. Each row/message looks up `display_names.get(class_name, class_name)`.

No change to `leaderboard.yaml` schema or contents — disambiguation is computed
at render time only.

## Error / Edge Handling

- **Unique names**: rendered bare; output byte-identical to today (verified by a
  no-collision regression test).
- **Empty username on collision**: class-name fallback (always unique).
- **Same author, same name**: username non-unique within group → class-name
  fallback for all members.
- **Class in `wins` but absent from `players`** (defensive): lookup falls back to
  the class name.

## Testing (TDD)

Unit tests for `build_display_names`:

- all-unique input → no suffixes, identity-ish map
- two distinct usernames → each suffixed with its username
- empty username in a colliding pair → class-name fallback for the empty one,
  username for the other
- both empty → class-name for both
- same username (same author) → class-name for both
- a non-colliding name alongside a colliding group → bare name preserved

Plus a regression check that rendering a no-collision leaderboard produces the
same output as before this change.

## Out of Scope

- No `leaderboard.yaml` schema change.
- No change to registration/validation (the parens-reservation rule is a
  separate branch).
- No backfill of the empty seed usernames (Alice/Bruno/Cleo/Diego) — those are
  unique names today so never trigger a suffix; the user will fix them
  separately.
