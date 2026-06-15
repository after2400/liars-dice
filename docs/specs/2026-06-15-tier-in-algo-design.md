# Tier-in-Algo Design Spec

**Goal:** Expose the current league tier (`"L1"`, `"CH"`, `"PRM"`) to player `algo()` methods as an opt-in parameter, enabling per-tier strategy calibration.

**Scope:** Detection refactor in `script.py` + `tier` threading through `series.py` and `__main__.py` + player authoring docs. No changes to `run_season.py`, `reset_season.py`, or any existing player.

**Architecture:** `args.tier` is already available in `game/__main__.py` (used for player filtering). It is simply not forwarded to `run_series()` or the engine. This spec closes that gap by threading `tier` through three files and switching `game_orchestrator`'s opt-in detection from position-count to parameter-name-based, which makes the `stats` and `tier` opt-ins fully independent.

---

## 1. Detection Refactor — `script.py`

### Current (position-count)

```python
_wants_stats = {p: len(inspect.signature(p.algo).parameters) >= 6 for p in players}
```

**Problem:** Forces positional coupling — a player wanting `tier` but not `stats` must still declare a dummy `stats` parameter in position 6 to receive `tier` in position 7.

### New (parameter-name-based)

```python
_sigs = {p: inspect.signature(p.algo).parameters for p in players}
_wants_stats = {p: "stats" in _sigs[p] for p in players}
_wants_tier  = {p: "tier"  in _sigs[p] for p in players}
```

### Call site

Replace both conditional `player.algo(...)` branches with a single kwargs-based call:

```python
kwargs: dict = {}
if _wants_stats[player]:
    kwargs["stats"] = stats
if _wants_tier[player]:
    kwargs["tier"] = tier
action = player.algo(
    hands[player_idx], current_bet, total_dice, bet_history, completed_outcomes, **kwargs
)
```

**Backwards compatibility:** Existing players that declare `stats=None` as a 6th positional parameter have `"stats"` in their signature and continue to receive it. Players with 5 parameters receive neither. No existing player requires changes.

### `game_orchestrator` signature

```python
def game_orchestrator(
    players: list,
    game_id: int = 1,
    bet_history: list[dict] | None = None,
    outcomes: list[dict] | None = None,
    stats=None,
    tier: str | None = None,   # ← new
):
```

---

## 2. Threading — `series.py`

```python
def run_series(players: list, n_games: int, tier: str | None = None) -> dict[str, int]:
```

Pass `tier` through to `game_orchestrator`:

```python
winner = game_orchestrator(
    players, game_id=game_num, bet_history=bet_history, outcomes=outcomes, stats=stats, tier=tier
)
```

---

## 3. Threading — `game/__main__.py`

`args.tier` is already parsed. Pass it to `run_series`:

```python
wins = run_series(players, N_GAMES, tier=args.tier)
```

That is the only change to `__main__.py`.

---

## 4. Tier values

| Context                              | `tier` value                |
| ------------------------------------ | --------------------------- |
| Regular season — L1 games            | `"L1"`                      |
| Regular season — CH games            | `"CH"`                      |
| Regular season — PRM games           | `"PRM"`                     |
| Tournament pools (`reset_season.py`) | `None` (no `--tier` passed) |
| `game -m game` with no `--tier`      | `None`                      |

Players must handle `None` gracefully — this is enforced by the validation job (see §6). The recommended pattern:

```python
def algo(self, hand, prior_bet, total_dice, bet_history, outcomes, tier=None):
    multiplier = 0.85 if tier == "CH" else 0.82
    ...
```

---

## 5. Player authoring

### New optional signatures

A player may now declare any combination:

```python
# tier only (no stats)
def algo(self, hand, prior_bet, total_dice, bet_history, outcomes, tier=None): ...

# stats only (unchanged from today)
def algo(self, hand, prior_bet, total_dice, bet_history, outcomes, stats=None): ...

# both
def algo(self, hand, prior_bet, total_dice, bet_history, outcomes, stats=None, tier=None): ...
```

Order of `stats` and `tier` in the signature does not matter — detection is by parameter name.

### Docs to update

- `RULES.md` — add `tier` to the algo parameter table; note that `None` means tournament or unknown context
- `examples/` player template — show `tier=None` in the commented algo signature block

---

## 6. Validation

`game/validate.py` gains a new check: when the player class declares `tier` in its `algo` signature, the validator calls `algo` with `tier=None` and minimal synthetic state and verifies no exception is raised. This runs inside `register_player.py` before the leaderboard entry is written — a crashing player is rejected at registration, not discovered on Monday morning when tournament games pass `None`.

```python
if "tier" in inspect.signature(player_class.algo).parameters:
    try:
        instance = player_class()
        instance.algo([], None, 10, [], [], tier=None)
    except Exception as e:
        return f"algo() raised {type(e).__name__} when called with tier=None: {e}"
```

The synthetic call uses `prior_bet=None` (opening bid scenario) and empty history, which is the minimal valid game state. If the player's `tier` branch crashes on `None`, it would also crash in every tournament game — so this is the highest-value single test.

---

## 7. Testing

- `tests/test_main.py`: add a test that a player declaring `tier=None` receives the correct string when the engine is called with a known tier.
- `tests/test_main.py`: add a test that a player declaring neither `stats` nor `tier` is unaffected.
- `tests/test_main.py`: add a test that `stats` and `tier` can be requested independently (player with only `tier` gets tier but not stats, and vice versa).
- `tests/test_validate_player.py`: add a test that a player whose `algo` crashes on `tier=None` fails validation.
- No new player tests required — no existing player changes.

---

## 8. Out of scope

- Per-tier `stats` objects (stats are shared across the whole series regardless of tier)
- Exposing opponent tier histories to players
- Tournament pool identity (`None` is sufficient for now)
