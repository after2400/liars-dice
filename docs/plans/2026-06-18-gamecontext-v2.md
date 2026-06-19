# GameContext v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the growing list of opt-in kwargs on `algo()` with a single immutable `GameContext` object, giving players a stable, future-proof interface while fully isolating each player's view of game state.

**Architecture:** A new `GameContext` class provides all game data as read-only properties backed by immutable internal storage (tuples + `MappingProxyType`). The engine detects v1 vs v2 players by counting positional parameters in `algo()` and dispatches accordingly. History entries become `MappingProxyType` at creation time. A hard cutover removes v1 support at the Q4 2026 tournament Monday (2026-10-05); until then both paths coexist and `validate.py` emits deprecation warnings for v1 players.

**Tech Stack:** Python 3.14, `functools.cached_property`, `types.MappingProxyType`, `inspect.signature`, `pytest`, `uv run pytest`

## Global Constraints

- Always use `uv run python` — never bare `python` or `python3`
- Test runner: `just pytest tests/` for targeted runs; `just pytest-all` before any commit
- Commit types must be from `.commitlintrc.mjs` — `feat`, `fix`, `chore`, `ci`, `docs`, `perf`, `test`
- All PRs: `🤖 Co-Authored with [Claude Code](https://claude.com/claude-code)` in body footer
- Never mock the game engine in tests — use real `run_series` or `game_orchestrator` calls
- TDD: write failing test first, confirm it fails, then implement

---

## Design Record

### The Problem

Every new engine feature (stats, tier, round_players) adds another optional kwarg to `algo()`. Detection via `inspect.signature` sprawls. Players opt in by parameter name — easy to miss, easy to get wrong.

### The v2 Contract

```python
def algo(self, ctx: GameContext) -> Bet | None:
    ctx.hand           # list[int]        — your current dice (mutable copy)
    ctx.prior_bet      # Bet | None       — last bid placed, None if opener
    ctx.total_dice     # int              — total active dice
    ctx.bet_history    # list[dict]       — all accepted bids, oldest first (mutable copy of immutable entries)
    ctx.outcomes       # list[dict]       — all completed rounds (mutable copy of immutable entries)
    ctx.stats          # GameStats        — always present, never None
    ctx.tier           # str | None       — "L1" / "CH" / "PRM" / None in tournament pools
    ctx.round_players  # list[str]        — clockwise bid order this round, [0] is the opener
```

All fields always present. No opt-in. No kwargs.

### Immutability Layers

| Layer                      | Mechanism                                       | Prevents                                                   |
| -------------------------- | ----------------------------------------------- | ---------------------------------------------------------- |
| No public setter           | `@property` without setter                      | `ctx.hand = x` → `AttributeError`                          |
| Name mangling              | `self.__field` → `_GameContext__field`          | accidental `ctx.__field` access                            |
| Immutable internal storage | tuples for lists, MappingProxyType for dicts    | `ctx._GameContext__hand.append(x)` → no `.append` on tuple |
| Immutable history entries  | `MappingProxyType` at creation time in engine   | `ctx.bet_history[0]["player"] = "x"` → `TypeError`         |
| Per-instance list copies   | `@cached_property` returns `list(self.__field)` | mutations isolated to that player's ctx instance           |

A player who gets `ctx.bet_history` gets a fresh list copy (computed once per `ctx` instance, cached after first access). They can append to it freely — it only affects their own copy. The engine's internal tuple and the `MappingProxyType` entries are never reachable through the public API.

### Detection Mechanism

Count non-`self` positional parameters in `algo()`:

- **1 param** → v2 (`def algo(self, ctx)`)
- **≥ 4 params** → v1 (`def algo(self, hand, prior_bet, total_dice, bet_history, outcomes, ...)`)

Built once per game at the start of `game_orchestrator`, same pattern as existing `_wants_stats`.

### `stats` in v2

`ctx.stats` is always a `GameStats` instance — never `None`. If the engine receives `stats=None` (no-stats run), `GameContext.__init__` creates an empty `GameStats()`. This is the explicit v2 promise: players don't need to guard against `None`.

### History Entry Shape Changes

`bet_history` entries become `MappingProxyType`. The `hands` dict inside `outcomes` entries becomes a nested `MappingProxyType` with `tuple` values:

```python
# before
{"game": 1, "round": 1, "player": "Alice", "bet": Bet(...), "dice_count": 4}

# after (MappingProxyType — all existing key access works identically)
MappingProxyType({"game": 1, "round": 1, "player": "Alice", "bet": Bet(...), "dice_count": 4})

# outcomes "hands" before
{"Alice": [3, 3, 1, 2, 4]}

# outcomes "hands" after
MappingProxyType({"Alice": (3, 3, 1, 2, 4)})
```

**Breaking change for v1 players:** `outcome["hands"]["Alice"]` is now a `tuple`, not a `list`. Reading by index still works. `.sort()` / `.append()` will raise `AttributeError`. Note in migration guide and deprecation warning.

### Cutover

- **Announced:** when this PR merges — GitHub issue + wiki update + CONTRIBUTING.md
- **Transition:** v1 and v2 both work; `validate.py` emits a deprecation warning for v1 players
- **Cutover date:** 2026-10-05 (Q4 2026 tournament Monday)
- **Post-cutover:** separate PR removes v1 dispatch path entirely; `validate.py` rejects v1

---

## File Map

| File                         | Status     | Responsibility                                                                        |
| ---------------------------- | ---------- | ------------------------------------------------------------------------------------- |
| `game/components/context.py` | **Create** | `GameContext` class — properties, immutability, `__repr__`                            |
| `game/components/script.py`  | **Modify** | Wrap history entries in `MappingProxyType`; add v1/v2 detection; add v2 dispatch path |
| `game/validate.py`           | **Modify** | Detect v1 shape; emit deprecation warning with cutover date                           |
| `tests/test_context.py`      | **Create** | Isolation, immutability, and property behaviour tests for `GameContext`               |
| `tests/test_main.py`         | **Modify** | Add v2 dispatch test; add test that v1 player still works alongside v2                |
| `docs/wiki/Player-Guide.md`  | **Modify** | v2 API reference, migration table, cutover notice                                     |
| `CONTRIBUTING.md`            | **Modify** | Migration guide, cutover date                                                         |

---

## Task 1: `GameContext` class

**Files:**

- Create: `game/components/context.py`
- Create: `tests/test_context.py`

**Interfaces:**

- Produces: `GameContext(hand, prior_bet, total_dice, bet_history, outcomes, stats, tier, round_players)` — all positional or keyword; `bet_history` and `outcomes` are expected to be lists of `MappingProxyType` entries (but this is not enforced — callers are responsible)

---

- [ ] **Step 1: Write failing tests**

Create `tests/test_context.py`:

```python
import pytest
from types import MappingProxyType
from game.components.bets import Bet
from game.components.context import GameContext


def _ctx(**overrides):
    defaults = dict(
        hand=[1, 2, 3],
        prior_bet=None,
        total_dice=15,
        bet_history=[MappingProxyType({"game": 1, "round": 1, "player": "Alice"})],
        outcomes=[MappingProxyType({"game": 1, "round": 1, "bet_held": True})],
        stats=None,
        tier="PRM",
        round_players=["Alice", "Bob"],
    )
    return GameContext(**{**defaults, **overrides})


def test_hand_returns_list():
    assert isinstance(_ctx().hand, list)


def test_hand_returns_correct_values():
    assert _ctx(hand=[3, 3, 1]).hand == [3, 3, 1]


def test_hand_mutation_does_not_affect_ctx():
    ctx = _ctx(hand=[1, 2, 3])
    ctx.hand.append(99)
    assert ctx.hand == [1, 2, 3]


def test_hand_is_not_settable():
    with pytest.raises(AttributeError):
        _ctx().hand = [1, 2, 3]


def test_prior_bet_none():
    assert _ctx(prior_bet=None).prior_bet is None


def test_prior_bet_returned():
    bet = Bet(2, 3, "Alice")
    assert _ctx(prior_bet=bet).prior_bet is bet


def test_prior_bet_is_not_settable():
    with pytest.raises(AttributeError):
        _ctx().prior_bet = None


def test_total_dice_returned():
    assert _ctx(total_dice=12).total_dice == 12


def test_total_dice_is_not_settable():
    with pytest.raises(AttributeError):
        _ctx().total_dice = 99


def test_bet_history_returns_list():
    assert isinstance(_ctx().bet_history, list)


def test_bet_history_entries_are_readonly():
    ctx = _ctx()
    with pytest.raises(TypeError):
        ctx.bet_history[0]["player"] = "hacked"


def test_bet_history_list_mutation_isolated_between_instances():
    entries = [MappingProxyType({"game": 1})]
    ctx1 = _ctx(bet_history=entries)
    ctx2 = _ctx(bet_history=entries)
    ctx1.bet_history.append("injected")
    assert len(ctx2.bet_history) == 1


def test_bet_history_is_not_settable():
    with pytest.raises(AttributeError):
        _ctx().bet_history = []


def test_outcomes_entries_are_readonly():
    ctx = _ctx()
    with pytest.raises(TypeError):
        ctx.outcomes[0]["bet_held"] = False


def test_outcomes_is_not_settable():
    with pytest.raises(AttributeError):
        _ctx().outcomes = []


def test_stats_none_becomes_gamestats():
    from game.components.stats import GameStats
    assert isinstance(_ctx(stats=None).stats, GameStats)


def test_stats_is_not_settable():
    with pytest.raises(AttributeError):
        _ctx().stats = None


def test_tier_returned():
    assert _ctx(tier="CH").tier == "CH"


def test_tier_none_allowed():
    assert _ctx(tier=None).tier is None


def test_tier_is_not_settable():
    with pytest.raises(AttributeError):
        _ctx().tier = "PRM"


def test_round_players_returns_list():
    assert isinstance(_ctx().round_players, list)


def test_round_players_values():
    assert _ctx(round_players=["X", "Y"]).round_players == ["X", "Y"]


def test_round_players_mutation_isolated():
    ctx = _ctx(round_players=["Alice", "Bob"])
    ctx.round_players.append("Eve")
    assert ctx.round_players == ["Alice", "Bob"]


def test_round_players_is_not_settable():
    with pytest.raises(AttributeError):
        _ctx().round_players = []


def test_repr_contains_total_dice():
    assert "15" in repr(_ctx(total_dice=15))
```

- [ ] **Step 2: Run tests — confirm they all fail**

```bash
just pytest tests/test_context.py
```

Expected: `ImportError: cannot import name 'GameContext' from 'game.components.context'`

- [ ] **Step 3: Implement `game/components/context.py`**

```python
from __future__ import annotations

from functools import cached_property

from game.components.stats import GameStats


class GameContext:
    """Immutable per-turn game state passed to v2 algo() implementations.

    All fields are read-only. List fields return a fresh mutable copy on first
    access (cached per instance) — mutations stay local to the caller.
    History entries are MappingProxyType: dict keys are readable, not writable.
    """

    def __init__(
        self,
        hand: list[int],
        prior_bet,
        total_dice: int,
        bet_history: list,
        outcomes: list,
        stats: GameStats | None,
        tier: str | None,
        round_players: list[str],
    ) -> None:
        self.__hand = tuple(hand)
        self.__prior_bet = prior_bet
        self.__total_dice = total_dice
        self.__bet_history = tuple(bet_history)
        self.__outcomes = tuple(outcomes)
        self.__stats = stats if stats is not None else GameStats()
        self.__tier = tier
        self.__round_players = tuple(round_players)

    @cached_property
    def hand(self) -> list[int]:
        return list(self.__hand)

    @property
    def prior_bet(self):
        return self.__prior_bet

    @property
    def total_dice(self) -> int:
        return self.__total_dice

    @cached_property
    def bet_history(self) -> list:
        return list(self.__bet_history)

    @cached_property
    def outcomes(self) -> list:
        return list(self.__outcomes)

    @property
    def stats(self) -> GameStats:
        return self.__stats

    @property
    def tier(self) -> str | None:
        return self.__tier

    @cached_property
    def round_players(self) -> list[str]:
        return list(self.__round_players)

    def __repr__(self) -> str:
        return (
            f"GameContext(total_dice={self.__total_dice}, "
            f"prior_bet={self.__prior_bet!r}, "
            f"tier={self.__tier!r}, "
            f"round_players={list(self.__round_players)!r})"
        )
```

- [ ] **Step 4: Run tests — confirm all pass**

```bash
just pytest tests/test_context.py
```

Expected: all pass.

- [ ] **Step 5: Run full suite — confirm no regressions**

```bash
just pytest-all
```

Expected: all existing tests pass.

- [ ] **Step 6: Commit**

```bash
git add game/components/context.py tests/test_context.py
git commit -m "feat(game): add GameContext class for v2 algo() interface"
```

---

## Task 2: Wrap history entries in `MappingProxyType`

**Files:**

- Modify: `game/components/script.py`
- Test via: `tests/test_context.py` (existing) and inline assertions

**Interfaces:**

- Consumes: `GameContext` from Task 1 (not yet used in dispatch — that's Task 3)
- Produces: `bet_history` and `outcomes` lists whose entries are `MappingProxyType`; `outcomes[n]["hands"]` values are `tuple[int]`

---

- [ ] **Step 1: Write failing test in `tests/test_main.py`**

Add after the existing `test_bet_history_includes_dice_count` test:

```python
def test_bet_history_entries_are_read_only(tmp_path):
    """bet_history entries passed to players are MappingProxyType — writes raise TypeError."""
    import textwrap
    from types import MappingProxyType
    from game.components.series import run_series
    from game.components.utils import import_player_classes_from_dir

    player_src = textwrap.dedent("""
        from game.components.bets import Bet

        class MutationProbe:
            name = "MutationProbe"
            saw_readonly = []
            def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):
                if bet_history:
                    try:
                        bet_history[-1]["player"] = "hacked"
                        MutationProbe.saw_readonly.append(False)
                    except TypeError:
                        MutationProbe.saw_readonly.append(True)
                if prior_bet is None:
                    from game.components.bets import Bet
                    return Bet(1, 2, self.name)
                return None
    """)

    player_dir = tmp_path / "players"
    player_dir.mkdir()
    (player_dir / "probe.py").write_text(player_src)
    (player_dir / "__init__.py").write_text("")
    players = import_player_classes_from_dir(str(player_dir))

    class AlwaysBid:
        name = "AlwaysBid"
        def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):
            from game.components.bets import Bet
            if prior_bet is None:
                return Bet(1, 2, self.name)
            return Bet(prior_bet.quantity + 1, prior_bet.face, self.name)

    run_series(players + [AlwaysBid()], n_games=1)
    probe_cls = players[0].__class__
    assert len(probe_cls.saw_readonly) > 0, "MutationProbe never saw a bet_history entry"
    assert all(probe_cls.saw_readonly), "bet_history entries were writable — expected TypeError"


def test_outcomes_hands_values_are_tuples(tmp_path):
    """outcomes[n]['hands'] values are tuples, not lists."""
    import textwrap
    from game.components.series import run_series
    from game.components.utils import import_player_classes_from_dir

    player_src = textwrap.dedent("""
        from game.components.bets import Bet

        class HandsProbe:
            name = "HandsProbe"
            hand_types = []
            def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):
                for outcome in outcomes:
                    for dice in outcome["hands"].values():
                        HandsProbe.hand_types.append(type(dice).__name__)
                if prior_bet is None:
                    return Bet(1, 2, self.name)
                return None
    """)

    player_dir = tmp_path / "players"
    player_dir.mkdir()
    (player_dir / "handsprobe.py").write_text(player_src)
    (player_dir / "__init__.py").write_text("")
    players = import_player_classes_from_dir(str(player_dir))

    class AlwaysBid:
        name = "AlwaysBid"
        def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):
            from game.components.bets import Bet
            if prior_bet is None:
                return Bet(1, 2, self.name)
            return Bet(prior_bet.quantity + 1, prior_bet.face, self.name)

    run_series(players + [AlwaysBid()], n_games=2)
    probe_cls = players[0].__class__
    assert len(probe_cls.hand_types) > 0, "HandsProbe never saw an outcome"
    assert all(t == "tuple" for t in probe_cls.hand_types), (
        f"Expected all tuple, got: {set(probe_cls.hand_types)}"
    )
```

- [ ] **Step 2: Run tests — confirm they fail**

```bash
just pytest tests/test_main.py::test_bet_history_entries_are_read_only tests/test_main.py::test_outcomes_hands_values_are_tuples
```

Expected: both FAIL — entries are plain dicts today.

- [ ] **Step 3: Add `import types` to `script.py` and wrap entries**

At the top of `game/components/script.py`, add:

```python
import types
```

Find the `bet_history.append(` call (around line 167) and change:

```python
# before
bet_history.append(
    {
        "game": game_id,
        "round": round_num,
        "player": player.name,
        "bet": current_bet,
        "dice_count": dice_counts[player_idx],
    }
)
```

```python
# after
bet_history.append(
    types.MappingProxyType({
        "game": game_id,
        "round": round_num,
        "player": player.name,
        "bet": current_bet,
        "dice_count": dice_counts[player_idx],
    })
)
```

Find the `completed_outcomes.append(` call (around line 139) and change:

```python
# before
completed_outcomes.append(
    {
        "game": game_id,
        "round": round_num,
        "hands": {players[i].name: hands[i] for i in active_list},
        "final_bet": current_bet,
        "bidder": players[prev_bidder].name,
        "challenger": player.name,
        "bet_held": bet_held,
        "loser": players[loser].name,
    }
)
```

```python
# after
completed_outcomes.append(
    types.MappingProxyType({
        "game": game_id,
        "round": round_num,
        "hands": types.MappingProxyType(
            {players[i].name: tuple(hands[i]) for i in active_list}
        ),
        "final_bet": current_bet,
        "bidder": players[prev_bidder].name,
        "challenger": player.name,
        "bet_held": bet_held,
        "loser": players[loser].name,
    })
)
```

- [ ] **Step 4: Run the two new tests — confirm they pass**

```bash
just pytest tests/test_main.py::test_bet_history_entries_are_read_only tests/test_main.py::test_outcomes_hands_values_are_tuples
```

Expected: both PASS.

- [ ] **Step 5: Run full suite — confirm no regressions**

```bash
just pytest-all
```

Expected: all pass. If any existing test accesses `outcome["hands"]["name"]` and calls list methods on it, fix those tests to use tuple-compatible operations.

- [ ] **Step 6: Commit**

```bash
git add game/components/script.py tests/test_main.py
git commit -m "feat(game): make bet_history and outcomes entries immutable (MappingProxyType)"
```

---

## Task 3: v1/v2 detection and v2 dispatch in the engine

**Files:**

- Modify: `game/components/script.py`
- Modify: `tests/test_main.py`

**Interfaces:**

- Consumes: `GameContext` from Task 1
- Produces: v2 players receive a `GameContext` instance; v1 players receive positional args exactly as before

**Detection rule:** count non-`self` positional parameters (`POSITIONAL_ONLY` or `POSITIONAL_OR_KEYWORD`) in `algo`. If count == 1, it's v2. If count ≥ 4, it's v1.

---

- [ ] **Step 1: Write failing tests in `tests/test_main.py`**

Add after the existing `test_round_players_first_element_is_opener` test:

```python
def test_v2_player_receives_game_context(tmp_path):
    """A player with def algo(self, ctx) receives a GameContext instance."""
    import textwrap
    from game.components.context import GameContext
    from game.components.series import run_series
    from game.components.utils import import_player_classes_from_dir

    player_src = textwrap.dedent("""
        from game.components.bets import Bet

        class V2Player:
            name = "V2Player"
            received = []
            def algo(self, ctx):
                V2Player.received.append(type(ctx).__name__)
                if ctx.prior_bet is None:
                    return Bet(1, 2, self.name)
                return None
    """)

    player_dir = tmp_path / "players"
    player_dir.mkdir()
    (player_dir / "v2player.py").write_text(player_src)
    (player_dir / "__init__.py").write_text("")
    players = import_player_classes_from_dir(str(player_dir))

    class AlwaysBid:
        name = "AlwaysBid"
        def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):
            from game.components.bets import Bet
            if prior_bet is None:
                return Bet(1, 2, self.name)
            return Bet(prior_bet.quantity + 1, prior_bet.face, self.name)

    run_series(players + [AlwaysBid()], n_games=1)
    spy_cls = players[0].__class__
    assert len(spy_cls.received) > 0, "V2Player.algo was never called"
    assert all(t == "GameContext" for t in spy_cls.received), (
        f"Expected GameContext on every call, got: {spy_cls.received}"
    )


def test_v2_ctx_has_all_fields(tmp_path):
    """GameContext passed to v2 player has all expected fields populated."""
    import textwrap
    from game.components.stats import GameStats
    from game.components.series import run_series
    from game.components.utils import import_player_classes_from_dir

    player_src = textwrap.dedent("""
        from game.components.bets import Bet

        class FieldProbe:
            name = "FieldProbe"
            snapshots = []
            def algo(self, ctx):
                FieldProbe.snapshots.append({
                    "hand_type": type(ctx.hand).__name__,
                    "total_dice": ctx.total_dice,
                    "stats_type": type(ctx.stats).__name__,
                    "round_players_type": type(ctx.round_players).__name__,
                    "tier": ctx.tier,
                })
                if ctx.prior_bet is None:
                    return Bet(1, 2, self.name)
                return None
    """)

    player_dir = tmp_path / "players"
    player_dir.mkdir()
    (player_dir / "fieldprobe.py").write_text(player_src)
    (player_dir / "__init__.py").write_text("")
    players = import_player_classes_from_dir(str(player_dir))

    class AlwaysBid:
        name = "AlwaysBid"
        def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):
            from game.components.bets import Bet
            if prior_bet is None:
                return Bet(1, 2, self.name)
            return Bet(prior_bet.quantity + 1, prior_bet.face, self.name)

    run_series(players + [AlwaysBid()], n_games=1, tier="CH")
    probe_cls = players[0].__class__
    assert len(probe_cls.snapshots) > 0
    for snap in probe_cls.snapshots:
        assert snap["hand_type"] == "list"
        assert snap["total_dice"] > 0
        assert snap["stats_type"] == "GameStats"
        assert snap["round_players_type"] == "list"
        assert snap["tier"] == "CH"


def test_v1_and_v2_players_coexist(tmp_path):
    """A v1 and v2 player in the same game both work correctly."""
    import textwrap
    from game.components.context import GameContext
    from game.components.series import run_series
    from game.components.utils import import_player_classes_from_dir

    v1_src = textwrap.dedent("""
        from game.components.bets import Bet

        class V1Player:
            name = "V1Player"
            calls = 0
            def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):
                V1Player.calls += 1
                if prior_bet is None:
                    return Bet(1, 2, self.name)
                return None
    """)

    v2_src = textwrap.dedent("""
        from game.components.bets import Bet

        class V2Player2:
            name = "V2Player2"
            calls = 0
            def algo(self, ctx):
                V2Player2.calls += 1
                if ctx.prior_bet is None:
                    return Bet(1, 2, self.name)
                return None
    """)

    player_dir = tmp_path / "players"
    player_dir.mkdir()
    (player_dir / "v1player.py").write_text(v1_src)
    (player_dir / "v2player2.py").write_text(v2_src)
    (player_dir / "__init__.py").write_text("")
    players = import_player_classes_from_dir(str(player_dir))

    run_series(players, n_games=3)
    v1_cls = next(p.__class__ for p in players if type(p).__name__ == "V1Player")
    v2_cls = next(p.__class__ for p in players if type(p).__name__ == "V2Player2")
    assert v1_cls.calls > 0, "V1Player was never called"
    assert v2_cls.calls > 0, "V2Player2 was never called"
```

- [ ] **Step 2: Run tests — confirm they fail**

```bash
just pytest tests/test_main.py::test_v2_player_receives_game_context tests/test_main.py::test_v2_ctx_has_all_fields tests/test_main.py::test_v1_and_v2_players_coexist
```

Expected: all FAIL — v2 players currently receive positional args and crash.

- [ ] **Step 3: Add v2 detection and dispatch to `game/components/script.py`**

At the top of the file, add import:

```python
from game.components.context import GameContext
```

In `game_orchestrator`, immediately after the existing `_wants_round_players` line, add:

```python
def _positional_count(params: dict) -> int:
    return sum(
        1 for name, p in params.items()
        if name != "self"
        and p.kind in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        )
    )

_is_v2 = {p: _positional_count(_sigs[p]) == 1 for p in players}
```

Replace the `try:` block inside the inner `while loser is None:` loop (the `kwargs: dict = {}` section) with:

```python
try:
    safe_bet = (
        Bet(current_bet.quantity, current_bet.face, current_bet.player)
        if current_bet is not None
        else None
    )
    if _is_v2[player]:
        ctx = GameContext(
            hand=list(hands[player_idx]),
            prior_bet=safe_bet,
            total_dice=total_dice,
            bet_history=bet_history,
            outcomes=completed_outcomes,
            stats=stats,
            tier=tier,
            round_players=round_players_order,
        )
        action = player.algo(ctx)
    else:
        kwargs: dict = {}
        if _wants_stats[player]:
            kwargs["stats"] = stats
        if _wants_tier[player]:
            kwargs["tier"] = tier
        if _wants_round_players[player]:
            kwargs["round_players"] = list(round_players_order)
        action = player.algo(
            list(hands[player_idx]),
            safe_bet,
            total_dice,
            list(bet_history),
            list(completed_outcomes),
            **kwargs,
        )
```

Note: remove the old `safe_bet` assignment that appears just before the current `kwargs: dict = {}` line — it moves inside the try block above.

- [ ] **Step 4: Run the three new tests — confirm they pass**

```bash
just pytest tests/test_main.py::test_v2_player_receives_game_context tests/test_main.py::test_v2_ctx_has_all_fields tests/test_main.py::test_v1_and_v2_players_coexist
```

Expected: all PASS.

- [ ] **Step 5: Run full suite**

```bash
just pytest-all
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add game/components/script.py tests/test_main.py
git commit -m "feat(game): dispatch GameContext to v2 algo() players"
```

---

## Task 4: Deprecation warning in `validate.py`

**Files:**

- Modify: `game/validate.py`
- Modify: `tests/test_validate_player.py`

**Interfaces:**

- Consumes: `inspect.signature` result for `algo`
- Produces: prints a deprecation warning to stdout when a v1 player is validated; exits 0 (warning only, not an error)

---

- [ ] **Step 1: Read `game/validate.py` to understand current structure**

```bash
just pytest tests/test_validate_player.py  # run existing tests to confirm baseline
```

Then read the file:

```bash
uv run python -c "import inspect, game.validate; print(inspect.getsourcefile(game.validate))"
```

- [ ] **Step 2: Write failing test in `tests/test_validate_player.py`**

Add at the end of the file:

```python
def test_v1_player_emits_deprecation_warning(tmp_path, capsys):
    """validate emits a deprecation warning for v1 algo() signatures."""
    player_src = textwrap.dedent("""
        from game.components.bets import Bet

        class LegacyPlayer:
            name = "LegacyPlayer"
            def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):
                if prior_bet is None:
                    return Bet(1, 2, self.name)
                return None
    """)
    player_file = tmp_path / "legacyplayer.py"
    player_file.write_text(player_src)

    result = subprocess.run(
        ["uv", "run", "python", "-m", "game.validate", str(player_file)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert result.returncode == 0, f"validate failed: {result.stderr}"
    assert "deprecated" in result.stdout.lower() or "deprecat" in result.stderr.lower(), (
        f"Expected deprecation warning, got stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert "2026-10-05" in result.stdout or "2026-10-05" in result.stderr, (
        "Expected cutover date in deprecation warning"
    )


def test_v2_player_no_deprecation_warning(tmp_path, capsys):
    """validate does not emit a deprecation warning for v2 algo() signatures."""
    player_src = textwrap.dedent("""
        from game.components.bets import Bet

        class ModernPlayer:
            name = "ModernPlayer"
            def algo(self, ctx):
                if ctx.prior_bet is None:
                    return Bet(1, 2, self.name)
                return None
    """)
    player_file = tmp_path / "modernplayer.py"
    player_file.write_text(player_src)

    result = subprocess.run(
        ["uv", "run", "python", "-m", "game.validate", str(player_file)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert result.returncode == 0, f"validate failed: {result.stderr}"
    assert "deprecat" not in result.stdout.lower()
    assert "deprecat" not in result.stderr.lower()
```

- [ ] **Step 3: Run tests — confirm they fail**

```bash
just pytest tests/test_validate_player.py::test_v1_player_emits_deprecation_warning tests/test_validate_player.py::test_v2_player_no_deprecation_warning
```

Expected: first test FAILS (no warning today); second test may pass or fail depending on whether validate crashes on `def algo(self, ctx)`.

- [ ] **Step 4: Add deprecation check to `game/validate.py`**

Locate where `validate.py` inspects the `algo` signature after instantiating the player. Add after the existing signature check succeeds:

```python
import inspect as _inspect

_algo_params = _inspect.signature(player_instance.algo).parameters
_positional = [
    name for name, p in _algo_params.items()
    if name != "self"
    and p.kind in (
        _inspect.Parameter.POSITIONAL_ONLY,
        _inspect.Parameter.POSITIONAL_OR_KEYWORD,
    )
]
if len(_positional) != 1:
    print(
        f"[DEPRECATION WARNING] {class_name} uses the v1 algo() interface "
        f"(positional args: {', '.join(_positional)}). "
        f"Migrate to def algo(self, ctx) before 2026-10-05 or this player "
        f"will be dropped from the league. "
        f"See: https://github.com/after2400/liars-dice/wiki/Player-Guide"
    )
```

- [ ] **Step 5: Run tests — confirm they pass**

```bash
just pytest tests/test_validate_player.py::test_v1_player_emits_deprecation_warning tests/test_validate_player.py::test_v2_player_no_deprecation_warning
```

Expected: both PASS.

- [ ] **Step 6: Run full suite**

```bash
just pytest-all
```

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add game/validate.py tests/test_validate_player.py
git commit -m "feat(game): emit v1 algo() deprecation warning in validate (cutover 2026-10-05)"
```

---

## Task 5: Documentation

**Files:**

- Modify: `docs/wiki/Player-Guide.md`
- Modify: `CONTRIBUTING.md`

No tests for this task. Docs are reviewed visually.

---

- [ ] **Step 1: Update `docs/wiki/Player-Guide.md`**

Add a **Deprecation notice** banner directly below the page header:

```markdown
> **Action required by 2026-10-05:** The v1 `algo()` interface (positional args) is deprecated. Migrate to the v2 `GameContext` interface before the Q4 2026 tournament Monday or your player will be dropped from the league. See [Migration Guide](#migrating-from-v1-to-v2) below.
```

Update the signature example under "Submitting a Player" to show v2:

```python
from game.components.bets import Bet

class Fred:
    name = "Fred the Magnificent"  # optional — defaults to class name

    def algo(self, ctx) -> Bet | None:
        # ctx.hand, ctx.prior_bet, ctx.total_dice, ctx.bet_history,
        # ctx.outcomes, ctx.stats, ctx.tier, ctx.round_players
        ...
```

Replace the `algo inputs` table with:

```markdown
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
```

Add a **Migration Guide** section before "Testing Locally":

````markdown
## Migrating from v1 to v2

The v1 interface used positional arguments:

```python
# v1 — deprecated, removed 2026-10-05
def algo(self, hand, prior_bet, total_dice, bet_history, outcomes, stats=None, tier=None, round_players=None):
    ...
```
````

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

````

- [ ] **Step 2: Update `CONTRIBUTING.md`**

Add a note under "Running Locally" pointing to the wiki migration guide and repeating the cutover date:

```markdown
> **Player API:** The v1 `algo()` positional-arg interface is deprecated. See the [Player Guide](https://github.com/after2400/liars-dice/wiki/Player-Guide#migrating-from-v1-to-v2) for migration instructions. Cutover: 2026-10-05.
````

- [ ] **Step 3: Commit**

```bash
git add docs/wiki/Player-Guide.md CONTRIBUTING.md
git commit -m "docs: add v2 GameContext API reference and v1 migration guide (cutover 2026-10-05)"
```

---

## Self-Review

**Spec coverage check:**

| Requirement                                    | Covered by                        |
| ---------------------------------------------- | --------------------------------- |
| `GameContext` class with all 8 fields          | Task 1                            |
| Immutable internal storage (tuples)            | Task 1 — `__init__` stores tuples |
| `@property` / `@cached_property` on all fields | Task 1                            |
| Name mangling (`self.__field`)                 | Task 1                            |
| `MappingProxyType` on history entries          | Task 2                            |
| `tuple` values in `outcomes["hands"]`          | Task 2                            |
| v1/v2 detection by param count                 | Task 3                            |
| v2 dispatch (pass `GameContext`)               | Task 3                            |
| v1 path preserved unchanged                    | Task 3                            |
| `stats=None` → empty `GameStats()` in v2       | Task 1 (`__init__`)               |
| Deprecation warning in `validate.py`           | Task 4                            |
| Cutover date 2026-10-05 in warning             | Task 4                            |
| v2 player validated without warning            | Task 4                            |
| Wiki API reference updated                     | Task 5                            |
| Migration guide (v1→v2 diff)                   | Task 5                            |
| `outcome["hands"]` tuple noted in docs         | Task 5                            |

**Out of scope (future PR at cutover):**

- Removing v1 dispatch path from `script.py`
- Removing `_wants_stats`, `_wants_tier`, `_wants_round_players` dicts
- Changing `validate.py` to reject v1 outright

**Placeholder scan:** none found.

**Type consistency:** `GameContext` constructor params match the `_ctx()` helper in tests and the dispatch in Task 3. `_positional_count` helper defined inline in Task 3 (not shared with Task 4 — Task 4 reimplements inline in `validate.py` to avoid cross-module coupling).
