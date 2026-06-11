# Relegation Cascade Settlement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the nightly season run rebalance the ladder in a single run by moving relegations out of the per-tier bottom-up pass into one top-down settlement pass with parachutist protection.

**Architecture:** Promotions stay in-pass (bottom-up, unchanged) inside `apply_season_results`. A new `settle_relegations` runs once after all tiers play, walking `PRM → CH → L1` and shedding each tier's excess over capacity into the tier below; a player dropped in from above this pass is protected from a second drop. `run_season` calls it after its tier loop. Dead code from abandoned approaches (`apply_pending_relegation`, `update_leaderboard`, `detect_phase`) is deleted.

**Tech Stack:** Python 3.11, PyYAML, pytest. Always run Python via `uv run` (project rule).

**Design doc:** `docs/specs/2026-06-11-relegation-cascade-settlement-design.md`

---

## Background the engineer needs

- **Leaderboard** is `leaderboard.yaml`: `{total_runs, last_updated, players: {ClassName: {display_name, github_username, date_added, tier, tier_since, times_inactive, tier_stats}}}`. `tier_stats` is `{tier: {wins, games, win_pct}}` accumulated over all time. Players are keyed by class name.
- **Tiers**, low→high: `inactive`, `L1`, `CH`, `PRM`. Capacities: `PRM=TOP_N`, `CH=TOP_N`, `L1=TOP_N×2`, `inactive=unbounded`. These come from `_TIER_CAPACITY(tier, top_n)` in `game/components/leaderboard.py`.
- **`_TIER_ABOVE` / `_TIER_BELOW`** (module constants in `game/components/leaderboard.py`) map a tier to its neighbour: `_TIER_BELOW = {"PRM": "CH", "CH": "L1", "L1": "inactive"}`.
- **`build_display_names(players)`** returns `{class_name: render_string}`, disambiguating shared display names. Movement strings use it.
- **`_now()`** returns an ISO-8601 UTC timestamp string.
- The season driver `.github/scripts/run_season.py` runs tiers bottom-up, calling `apply_season_results` per tier, and collects `tier_results: dict[tier, dict[player, win_count]]` (this run's wins per tier). That dict is exactly what settlement needs to know who played each tier and how they ranked.
- **Run tests with `uv run pytest -v`** (no path — `pyproject.toml` `testpaths` collects both `tests/` and `examples/tests/`).

---

## File structure

| File                             | Responsibility        | Change                                                                                                                                          |
| -------------------------------- | --------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| `game/components/leaderboard.py` | tier movement logic   | Strip relegation from `apply_season_results`; add `settle_relegations`; delete `apply_pending_relegation`, `update_leaderboard`, `detect_phase` |
| `.github/scripts/run_season.py`  | nightly orchestration | Call `settle_relegations` after the tier loop; print its movements under a `[settle]` line                                                      |
| `tests/test_leaderboard.py`      | unit tests            | Add `settle_relegations` tests; adjust `apply_season_results` tests; delete tests for removed functions                                         |
| `tests/test_run_season.py` (new) | integration test      | End-to-end run with a faked game engine proving the worked example                                                                              |
| `tests/conftest.py`              | fixtures              | Delete fixtures left unused after test deletions (`lb_with_pending`, `lb_file`)                                                                 |

---

## Task 1: Add `settle_relegations`

**Files:**

- Modify: `game/components/leaderboard.py` (add new function near the bottom, after `apply_season_results`)
- Test: `tests/test_leaderboard.py` (append a new test section)

This task is purely additive — nothing calls `settle_relegations` yet, so the suite stays green.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_leaderboard.py`:

```python
# --- settle_relegations ---


def _p(tier, since="2026-01-01T00:00:00Z", games=0):
    """Minimal player record for settlement tests."""
    return {
        "display_name": None,  # filled in by caller via dict key below
        "github_username": "",
        "date_added": "2026-01-01T00:00:00Z",
        "tier": tier,
        "tier_since": since,
        "times_inactive": 0,
        "tier_stats": {tier: {"wins": 0, "games": games, "win_pct": 0.0}} if games else {},
    }


def _write(tmp_path, players):
    for name, rec in players.items():
        rec["display_name"] = name
    data = {"total_runs": 1, "last_updated": "2026-01-01T00:00:00Z", "players": players}
    path = str(tmp_path / "lb.yaml")
    (tmp_path / "lb.yaml").write_text(yaml.dump(data))
    return path


def test_settle_cascade_one_pass(tmp_path):
    """PRM overflow drops to CH; CH then overflows and drops its worst player to L1."""
    from game.components.leaderboard import settle_relegations

    players = {
        # PRM has 5 (one too many): Remy is the parachutee-to-be (worst this run)
        "Diego": _p("PRM"), "Eva": _p("PRM"), "Sloane": _p("PRM"), "Zara": _p("PRM"),
        "Remy": _p("PRM"),
        # CH has 4 incl. Cleo (promoted in this run, flopped); Alice/Bruno/Finn natives
        "Alice": _p("CH"), "Bruno": _p("CH"), "Finn": _p("CH"), "Cleo": _p("CH"),
        # L1 under capacity
        "Pyro": _p("L1"), "Topper": _p("L1"),
    }
    path = _write(tmp_path, players)
    tier_results = {
        "PRM": {"Sloane": 240, "Eva": 235, "Zara": 217, "Diego": 202, "Remy": 106},
        "CH": {"Remy": 337, "Finn": 312, "Alice": 194, "Bruno": 153, "Cleo": 4},
        "L1": {"Cleo": 471, "Topper": 444, "Pyro": 85},
    }
    moves = settle_relegations(tier_results, top_n=4, path=path)

    with open(path) as f:
        result = yaml.safe_load(f)["players"]
    assert result["Remy"]["tier"] == "CH"   # PRM → CH
    assert result["Cleo"]["tier"] == "L1"    # CH → L1 (worst CH player)
    assert {n for n, p in result.items() if p["tier"] == "PRM"} == {"Diego", "Eva", "Sloane", "Zara"}
    assert {n for n, p in result.items() if p["tier"] == "CH"} == {"Alice", "Bruno", "Finn", "Remy"}
    assert {n for n, p in result.items() if p["tier"] == "L1"} == {"Pyro", "Topper", "Cleo"}
    assert moves == ["Relegated: Remy → CH", "Relegated: Cleo → L1"]


def test_settle_protects_parachutist(tmp_path):
    """A player dropped from above is not re-dropped; the worst native drops instead."""
    from game.components.leaderboard import settle_relegations

    players = {
        "Diego": _p("PRM"), "Eva": _p("PRM"), "Sloane": _p("PRM"), "Zara": _p("PRM"),
        "Remy": _p("PRM"),
        "Alice": _p("CH"), "Bruno": _p("CH"), "Finn": _p("CH"), "Cleo": _p("CH"),
        "Pyro": _p("L1"), "Topper": _p("L1"),
    }
    path = _write(tmp_path, players)
    # Remy wins CH big (337) — if he were eligible in CH he'd be safe anyway; the point is
    # he is excluded as a parachutist, so the worst native (Cleo) drops even though Remy
    # also has a CH result this run.
    tier_results = {
        "PRM": {"Sloane": 240, "Eva": 235, "Zara": 217, "Diego": 202, "Remy": 106},
        "CH": {"Remy": 337, "Finn": 312, "Alice": 194, "Bruno": 153, "Cleo": 4},
    }
    settle_relegations(tier_results, top_n=4, path=path)
    with open(path) as f:
        result = yaml.safe_load(f)["players"]
    assert result["Remy"]["tier"] == "CH"   # stayed where he parachuted
    assert result["Cleo"]["tier"] == "L1"   # native worst dropped


def test_settle_no_relegation_at_capacity(tmp_path):
    """Tiers at or under capacity shed nobody."""
    from game.components.leaderboard import settle_relegations

    players = {
        "Alice": _p("PRM"), "Bruno": _p("PRM"),
        "Cleo": _p("CH"), "Diego": _p("CH"),
    }
    path = _write(tmp_path, players)
    tier_results = {"PRM": {"Alice": 70, "Bruno": 30}, "CH": {"Cleo": 60, "Diego": 40}}
    moves = settle_relegations(tier_results, top_n=2, path=path)
    assert moves == []
    with open(path) as f:
        result = yaml.safe_load(f)["players"]
    assert all(result[n]["tier"] == t for n, t in
               {"Alice": "PRM", "Bruno": "PRM", "Cleo": "CH", "Diego": "CH"}.items())


def test_settle_l1_to_inactive_only_when_over_double(tmp_path):
    """L1 relegates to inactive only past TOP_N×2, and increments times_inactive."""
    from game.components.leaderboard import settle_relegations

    # TOP_N=2 → L1 capacity 4. Five L1 players → one drops to inactive.
    players = {f"P{i}": _p("L1") for i in range(5)}
    path = _write(tmp_path, players)
    tier_results = {"L1": {"P0": 50, "P1": 40, "P2": 30, "P3": 20, "P4": 5}}
    moves = settle_relegations(tier_results, top_n=2, path=path)
    with open(path) as f:
        result = yaml.safe_load(f)["players"]
    assert result["P4"]["tier"] == "inactive"   # worst L1 player
    assert result["P4"]["times_inactive"] == 1
    assert moves == ["Relegated: P4 → inactive"]


def test_settle_movement_uses_disambiguated_name(tmp_path):
    """Movement strings render disambiguated display names for shared names."""
    from game.components.leaderboard import settle_relegations

    players = {
        "Eva": _p("PRM"), "Zara": _p("PRM"), "Sloane": _p("PRM"),
        "Diego": _p("PRM"), "Remy": _p("PRM"),
        "Alice": _p("CH"), "Bruno": _p("CH"),
    }
    for name, rec in players.items():
        rec["display_name"] = name
    # Two players share display_name "Twin" so the suffix logic engages.
    players["Remy"]["display_name"] = "Twin"
    players["Alice"]["display_name"] = "Twin"
    players["Remy"]["github_username"] = "remy_gh"
    data = {"total_runs": 1, "last_updated": "2026-01-01T00:00:00Z", "players": players}
    path = str(tmp_path / "lb.yaml")
    (tmp_path / "lb.yaml").write_text(yaml.dump(data))

    tier_results = {"PRM": {"Eva": 50, "Zara": 40, "Sloane": 30, "Diego": 20, "Remy": 5}}
    moves = settle_relegations(tier_results, top_n=4, path=path)
    assert moves == ["Relegated: Twin (remy_gh) → CH"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_leaderboard.py -k settle -v`
Expected: FAIL — `ImportError`/`cannot import name 'settle_relegations'`.

- [ ] **Step 3: Implement `settle_relegations`**

In `game/components/leaderboard.py`, add this function immediately after `apply_season_results` (keep the existing `_TIER_ABOVE`, `_TIER_BELOW`, `_TIER_CAPACITY` definitions above it):

```python
def settle_relegations(
    tier_results: dict[str, dict[str, int]],
    top_n: int,
    path: str = _LEADERBOARD_PATH,
) -> list[str]:
    """Top-down relegation settlement, run once after a full bottom-up season.

    Walks PRM → CH → L1. Each tier sheds its excess over capacity into the tier
    below, choosing the worst performers who actually PLAYED that tier this run.
    A player relegated into a tier during this pass (a "parachutist") holds a
    protected seat and is not re-relegated the same night.

    tier_results: {tier: {player: win_count}} for this run's games — used to
        rank who played worst in each tier.
    Returns "Relegated: <name> → <tier>" movement strings, in cascade order.
    """
    if os.path.exists(path):
        with open(path) as f:
            data = yaml.safe_load(f) or {}
    else:
        data = {}

    now = _now()
    data.setdefault("players", {})
    players = data["players"]
    display_names = build_display_names(players)

    parachutists: dict[str, set[str]] = {}
    movements: list[str] = []

    for tier in ("PRM", "CH", "L1"):
        tier_below = _TIER_BELOW.get(tier)
        if tier_below is None:
            continue
        capacity = _TIER_CAPACITY(tier, top_n)
        residents = [n for n, p in players.items() if p.get("tier") == tier]
        excess = int(len(residents) - capacity)
        if excess <= 0:
            continue

        protected = parachutists.get(tier, set())
        this_season = tier_results.get(tier, {})
        candidates = [n for n in residents if n in this_season and n not in protected]

        # Worst-first ordering. Python's sort is stable, so sort by the
        # least-significant key first: tier_since DESC (newest first), then by
        # (this-season wins ASC, total tier games ASC).
        candidates.sort(key=lambda n: players[n].get("tier_since", ""), reverse=True)
        candidates.sort(
            key=lambda n: (
                this_season[n],
                players[n].get("tier_stats", {}).get(tier, {}).get("games", 0),
            )
        )

        assert len(candidates) >= excess, (
            f"{tier} over capacity by {excess} but only {len(candidates)} "
            f"relegation candidate(s) — upstream invariant broken"
        )

        for name in candidates[:excess]:
            players[name]["tier"] = tier_below
            players[name]["tier_since"] = now
            if tier_below == "inactive":
                players[name]["times_inactive"] = players[name].get("times_inactive", 0) + 1
            parachutists.setdefault(tier_below, set()).add(name)
            movements.append(f"Relegated: {display_names.get(name, name)} → {tier_below}")

    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    return movements
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_leaderboard.py -k settle -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Run the full suite**

Run: `uv run pytest -v`
Expected: PASS — no regressions (the new function is not yet wired in).

- [ ] **Step 6: Commit**

```bash
git add game/components/leaderboard.py tests/test_leaderboard.py
git commit -m "feat(leaderboard): add top-down relegation settlement"
```

---

## Task 2: Make `apply_season_results` promotion-only

**Files:**

- Modify: `game/components/leaderboard.py` — `apply_season_results` (remove the relegation block, currently the tail of the function)
- Test: `tests/test_leaderboard.py`

`apply_season_results` currently both promotes the tier winner and relegates excess. Relegation now belongs to `settle_relegations`, so strip it here.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_leaderboard.py`:

```python
def test_apply_season_results_does_not_relegate_when_overcrowded(tmp_path):
    """apply_season_results promotes the winner but never relegates — even when overcrowded."""
    from game.components.leaderboard import apply_season_results

    def _player(tier):
        return {
            "display_name": None, "github_username": "", "tier": tier,
            "tier_since": "2026-01-01T00:00:00Z", "date_added": "2026-01-01T00:00:00Z",
            "times_inactive": 0, "tier_stats": {},
        }

    # CH overcrowded: 3 players, capacity TOP_N=2.
    players = {"Alice": _player("CH"), "Bruno": _player("CH"), "Cleo": _player("CH")}
    for n, rec in players.items():
        rec["display_name"] = n
    lb = {"total_runs": 1, "last_updated": "2026-01-01T00:00:00Z", "players": players}
    path = str(tmp_path / "lb.yaml")
    (tmp_path / "lb.yaml").write_text(yaml.dump(lb))

    apply_season_results(
        wins={"Alice": 70, "Bruno": 20, "Cleo": 10}, n_games=100, tier="CH", top_n=2, path=path
    )
    with open(path) as f:
        result = yaml.safe_load(f)["players"]
    assert result["Alice"]["tier"] == "PRM"   # winner still promoted
    assert result["Bruno"]["tier"] == "CH"    # NOT relegated
    assert result["Cleo"]["tier"] == "CH"     # NOT relegated (settlement's job now)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_leaderboard.py::test_apply_season_results_does_not_relegate_when_overcrowded -v`
Expected: FAIL — current code relegates Cleo to L1, so `result["Cleo"]["tier"] == "CH"` is false.

- [ ] **Step 3: Remove the relegation block from `apply_season_results`**

In `game/components/leaderboard.py`, inside `apply_season_results`:

1. Delete the line `tier_below = _TIER_BELOW.get(tier)` (the `tier_above` line directly above it stays).
2. Delete the entire relegation block — the comment beginning `# Relegate only if remaining players exceed capacity after promotion.` through the end of its `for name in reversed(remaining):` loop. After the edit, the function ends with the promotion block, then:

```python
    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    return movements
```

The promotion block (kept) is:

```python
    # Promote top player unconditionally
    promoted = None
    if tier_above and players_in_tier:
        promoted = players_in_tier[0]
        data["players"][promoted]["tier"] = tier_above
        data["players"][promoted]["tier_since"] = now
        movements.append(f"Promoted: {_display(promoted)} → {tier_above}")
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/test_leaderboard.py::test_apply_season_results_does_not_relegate_when_overcrowded -v`
Expected: PASS.

- [ ] **Step 5: Delete the now-obsolete relegation test**

The scenario in `test_apply_season_results_relegates_when_truly_overcrowded` is now covered by the `settle_relegations` tests. Delete that whole test function from `tests/test_leaderboard.py`.

The three `test_apply_season_results_no_relegation_*` tests stay — they correctly assert `apply_season_results` does not relegate.

- [ ] **Step 6: Run the full suite**

Run: `uv run pytest -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add game/components/leaderboard.py tests/test_leaderboard.py
git commit -m "refactor(leaderboard): move relegation out of apply_season_results"
```

---

## Task 3: Wire settlement into `run_season` + end-to-end test

**Files:**

- Modify: `.github/scripts/run_season.py` (`run_season`, around the tier loop)
- Test: `tests/test_run_season.py` (new)

- [ ] **Step 1: Write the failing integration test**

Create `tests/test_run_season.py`:

```python
"""End-to-end run_season test with a faked game engine.

Monkeypatches _run_tier so no subprocess/game is needed; asserts the full
bottom-up promotion + top-down settlement produces a balanced ladder.
"""

import importlib.util
from pathlib import Path

import yaml

# Load run_season.py by path (it lives under .github/scripts, not an import package).
_SCRIPT = Path(__file__).parent.parent / ".github" / "scripts" / "run_season.py"
_spec = importlib.util.spec_from_file_location("run_season", _SCRIPT)
run_season_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(run_season_mod)


def _player(tier):
    return {
        "display_name": None, "github_username": "", "date_added": "2026-01-01T00:00:00Z",
        "tier": tier, "tier_since": "2026-01-01T00:00:00Z", "times_inactive": 0, "tier_stats": {},
    }


def test_run_season_rebalances_in_one_run(tmp_path, monkeypatch):
    players = {
        "Diego": _player("PRM"), "Eva": _player("PRM"), "Sloane": _player("PRM"), "Zara": _player("PRM"),
        "Alice": _player("CH"), "Bruno": _player("CH"), "Finn": _player("CH"), "Remy": _player("CH"),
        "Cleo": _player("L1"), "Pyro": _player("L1"), "Topper": _player("L1"),
    }
    for n, rec in players.items():
        rec["display_name"] = n
    lb_path = str(tmp_path / "leaderboard.yaml")
    (tmp_path / "leaderboard.yaml").write_text(
        yaml.dump({"total_runs": 0, "last_updated": "x", "players": players})
    )

    # Canned per-tier win counts. Cleo wins L1 (promoted), flops in CH;
    # Remy wins CH (promoted), flops in PRM.
    canned = {
        "L1": {"Cleo": 471, "Topper": 444, "Pyro": 85},
        "CH": {"Remy": 337, "Finn": 312, "Alice": 194, "Bruno": 153, "Cleo": 4},
        "PRM": {"Sloane": 240, "Eva": 235, "Zara": 217, "Diego": 202, "Remy": 106},
    }
    monkeypatch.setattr(run_season_mod, "_run_tier", lambda tier, n, t, p: canned.get(tier, {}))

    run_season_mod.run_season(
        n_games=1000, top_n=4, lb_path=lb_path,
        summary_file=str(tmp_path / "summary.md"),
        readme_path=str(tmp_path / "README.md"),  # no markers → README update is a no-op
    )

    result = yaml.safe_load(Path(lb_path).read_text())["players"]
    by_tier = lambda t: {n for n, p in result.items() if p["tier"] == t}
    assert by_tier("PRM") == {"Diego", "Eva", "Sloane", "Zara"}
    assert by_tier("CH") == {"Alice", "Bruno", "Finn", "Remy"}   # Remy parachuted back
    assert by_tier("L1") == {"Pyro", "Topper", "Cleo"}           # Cleo bounced back
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_run_season.py -v`
Expected: FAIL — without settlement, `CH` ends as `{Alice, Bruno, Finn, Cleo, Remy}` (5) and `L1` as `{Pyro, Topper}`.

- [ ] **Step 3: Wire `settle_relegations` into `run_season`**

In `.github/scripts/run_season.py`:

1. Change the import at the top of `run_season` from:

```python
    from game.components.leaderboard import apply_season_results
```

to:

```python
    from game.components.leaderboard import apply_season_results, settle_relegations
```

2. Immediately after the `for tier in tier_order:` loop ends and before `_write_summary(...)`, insert:

```python
    relegations = settle_relegations(tier_results, top_n, path=lb_path)
    if relegations:
        print("[settle] cross-tier relegations:")
        for m in relegations:
            print(f"  {m}")
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/test_run_season.py -v`
Expected: PASS.

- [ ] **Step 5: Run the full suite**

Run: `uv run pytest -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add .github/scripts/run_season.py tests/test_run_season.py
git commit -m "feat(scripts): apply relegation settlement after the season loop"
```

---

## Task 4: Delete dead code

**Files:**

- Modify: `game/components/leaderboard.py` (delete `apply_pending_relegation`, `update_leaderboard`, `detect_phase`)
- Modify: `tests/test_leaderboard.py` (delete their tests and imports)
- Modify: `tests/conftest.py` (delete fixtures left unused)

These three functions are referenced only by tests; nothing in the runtime path imports them (verified: `grep -rn "apply_pending_relegation\|update_leaderboard\|detect_phase" --include="*.py" .` shows only their defs and test usages).

- [ ] **Step 1: Delete the functions**

In `game/components/leaderboard.py`, delete these three functions in their entirety:

- `apply_pending_relegation(data)` (and its docstring)
- `detect_phase(data, top_n)` (and its docstring)
- `update_leaderboard(...)` (the whole function)

Keep everything else: `build_display_names`, `_now`, `get_tier_players`, `_TIER_ABOVE`, `_TIER_BELOW`, `_TIER_CAPACITY`, `apply_season_results`, `settle_relegations`, and the `_LEADERBOARD_PATH` constant.

- [ ] **Step 2: Delete their tests and imports**

In `tests/test_leaderboard.py`:

- Remove `apply_pending_relegation`, `detect_phase`, and `update_leaderboard` from the top-of-file import:

```python
from game.components.leaderboard import (
    get_tier_players,
)
```

- Delete the `# --- apply_pending_relegation ---` test block (the four `test_apply_pending_*` functions).
- Delete the `# --- detect_phase ---` test block (all `test_detect_phase_*` functions).
- Delete the `# --- update_leaderboard ---` test block (every `test_*` function that calls `update_leaderboard`, from `test_update_stats_for_competing_players` through the last one in that section, including `test_*` that uses the `lb_file` and the new-player creation test).

Keep the `# --- get_tier_players ---` tests and all `apply_season_results` / `settle_relegations` tests.

- [ ] **Step 3: Delete unused fixtures**

In `tests/conftest.py`, delete the `lb_with_pending` and `lb_file` fixtures — after Step 2 nothing references them. Keep `minimal_lb` (used by `get_tier_players` tests) and `full_two_tier_lb` (used by `get_tier_players` tests).

- [ ] **Step 4: Verify no dangling references**

Run: `uv run pytest -v`
Expected: PASS. If collection errors mention `lb_file`, `lb_with_pending`, `detect_phase`, `update_leaderboard`, or `apply_pending_relegation`, a reference was missed — remove it.

Also run: `grep -rn "apply_pending_relegation\|update_leaderboard\|detect_phase\|lb_with_pending\|lb_file" tests/ game/`
Expected: no matches.

- [ ] **Step 5: Commit**

```bash
git add game/components/leaderboard.py tests/test_leaderboard.py tests/conftest.py
git commit -m "refactor(leaderboard): delete unused pending-relegation, update_leaderboard, detect_phase"
```

---

## Final verification

- [ ] Run the full suite once more: `uv run pytest -v` — all green.
- [ ] Sanity-grep that settlement is wired: `grep -n settle_relegations .github/scripts/run_season.py` shows the import and the post-loop call.
- [ ] Hand off via `superpowers:finishing-a-development-branch` (branch already pushed work → choose "Push and create a Pull Request").

---

## Notes / out of scope (do not do)

- Promotion logic is unchanged — only relegation moves.
- Do **not** add phase-gating behavior; `detect_phase` is being deleted because nothing uses it.
- Do **not** touch `README.md` standings format, `_write_summary`, or `_update_readme` — their movement reconstruction reads the final (post-settlement) leaderboard and already reflects relegations correctly.
- `total_runs` / `last_updated` bookkeeping stays as-is; `settle_relegations` deliberately does not bump `total_runs` (it is part of the same run, not a new one).
