# Duplicate Player Name Display — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render player display names bare unless 2+ players share a name; on collision append a unique `(github_username)` / `(class_name)` suffix everywhere names appear.

**Architecture:** One pure helper `build_display_names(players)` in `game/components/leaderboard.py` maps each class name (the leaderboard key) to its render string, suffixing only names that collide across the whole leaderboard. Every render site builds the map once from the full players dict and looks up by class name. Render-time only; no `leaderboard.yaml` schema change.

**Tech Stack:** Python 3, pytest, PyYAML. Run everything with `uv run` (project rule — never bare `python`/`pytest`).

**Branch:** `feat/duplicate-name-display` (already created off `main`; the spec is already committed here).

---

## File Structure

| File                             | Responsibility                                                        | Change                                                          |
| -------------------------------- | --------------------------------------------------------------------- | --------------------------------------------------------------- |
| `game/components/leaderboard.py` | Owns the helper + uses it in `apply_season_results` movement messages | Modify                                                          |
| `.github/scripts/run_season.py`  | Season summary + README rendering                                     | Modify (`_standings_table`, `_write_summary`, `_update_readme`) |
| `tests/test_leaderboard.py`      | Unit tests for the helper + `apply_season_results` wiring             | Modify (append)                                                 |
| `tests/test_run_season.py`       | Functional tests for summary + README rendering                       | Modify (append)                                                 |

**Render sites covered (more than the spec's count — `_standings_table` is shared by 3 callers):**

- `leaderboard.py`: `apply_season_results._display()` (movement messages)
- `run_season.py` `_write_summary`: inactive list, game-results table, movements, standings (via `_standings_table`)
- `run_season.py` `_update_readme`: tier standings + inactive standings (both via `_standings_table`)

Fixing `_standings_table` once covers all three standings renders.

---

### Task 1: `build_display_names` helper

**Files:**

- Modify: `game/components/leaderboard.py` (imports + new function)
- Test: `tests/test_leaderboard.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_leaderboard.py`:

```python
def test_build_display_names_unique_names_unsuffixed():
    from game.components.leaderboard import build_display_names

    players = {
        "Alice": {"display_name": "Alice", "github_username": "x"},
        "Bruno": {"display_name": "Bruno", "github_username": "y"},
    }
    assert build_display_names(players) == {"Alice": "Alice", "Bruno": "Bruno"}


def test_build_display_names_distinct_usernames_get_suffix():
    from game.components.leaderboard import build_display_names

    players = {
        "TopperA": {"display_name": "Topper", "github_username": "after2400"},
        "TopperB": {"display_name": "Topper", "github_username": "jschmoe"},
    }
    assert build_display_names(players) == {
        "TopperA": "Topper (after2400)",
        "TopperB": "Topper (jschmoe)",
    }


def test_build_display_names_empty_username_falls_back_to_class():
    from game.components.leaderboard import build_display_names

    players = {
        "TopperA": {"display_name": "Topper", "github_username": "after2400"},
        "TopperB": {"display_name": "Topper", "github_username": ""},
    }
    assert build_display_names(players) == {
        "TopperA": "Topper (after2400)",
        "TopperB": "Topper (TopperB)",
    }


def test_build_display_names_both_empty_use_class():
    from game.components.leaderboard import build_display_names

    players = {
        "TopperA": {"display_name": "Topper", "github_username": ""},
        "TopperB": {"display_name": "Topper", "github_username": ""},
    }
    assert build_display_names(players) == {
        "TopperA": "Topper (TopperA)",
        "TopperB": "Topper (TopperB)",
    }


def test_build_display_names_same_author_uses_class():
    from game.components.leaderboard import build_display_names

    players = {
        "TopperA": {"display_name": "Topper", "github_username": "after2400"},
        "TopperB": {"display_name": "Topper", "github_username": "after2400"},
    }
    assert build_display_names(players) == {
        "TopperA": "Topper (TopperA)",
        "TopperB": "Topper (TopperB)",
    }


def test_build_display_names_mixed_collision_and_unique():
    from game.components.leaderboard import build_display_names

    players = {
        "TopperA": {"display_name": "Topper", "github_username": "after2400"},
        "TopperB": {"display_name": "Topper", "github_username": "jschmoe"},
        "Alice": {"display_name": "Alice", "github_username": ""},
    }
    result = build_display_names(players)
    assert result["Alice"] == "Alice"
    assert result["TopperA"] == "Topper (after2400)"
    assert result["TopperB"] == "Topper (jschmoe)"


def test_build_display_names_missing_display_name_uses_class():
    from game.components.leaderboard import build_display_names

    players = {"Solo": {"github_username": "x"}}
    assert build_display_names(players) == {"Solo": "Solo"}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_leaderboard.py -k build_display_names -v`
Expected: FAIL — `ImportError: cannot import name 'build_display_names'`

- [ ] **Step 3: Implement the helper**

In `game/components/leaderboard.py`, change the top imports from:

```python
import os
from datetime import datetime, timezone

import yaml
```

to:

```python
import os
from collections import Counter, defaultdict
from datetime import datetime, timezone

import yaml
```

Then add this function immediately after the imports (above `_now`):

```python
def build_display_names(players: dict) -> dict[str, str]:
    """Map each class name (leaderboard key) to its render string.

    A name is suffixed only when 2+ players share the same display_name. The
    suffix is the github_username when it is non-empty AND unique within the
    colliding group; otherwise it falls back to the class name, which is always
    unique. Unique names render bare.
    """
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

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_leaderboard.py -k build_display_names -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add game/components/leaderboard.py tests/test_leaderboard.py
git commit -m "feat(leaderboard): add build_display_names disambiguation helper"
```

---

### Task 2: Wire helper into `apply_season_results` movement messages

**Files:**

- Modify: `game/components/leaderboard.py` (`apply_season_results._display`)
- Test: `tests/test_leaderboard.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_leaderboard.py`:

```python
def test_apply_season_results_movement_uses_disambiguated_name(tmp_path):
    import yaml as _yaml

    from game.components.leaderboard import apply_season_results

    path = str(tmp_path / "lb.yaml")
    data = {
        "total_runs": 0,
        "players": {
            "TopperA": {
                "display_name": "Topper",
                "github_username": "alice",
                "tier": "CH",
                "tier_since": "2026-01-01T00:00:00Z",
                "tier_stats": {},
            },
            "TopperB": {
                "display_name": "Topper",
                "github_username": "bob",
                "tier": "CH",
                "tier_since": "2026-01-01T00:00:00Z",
                "tier_stats": {},
            },
        },
    }
    (tmp_path / "lb.yaml").write_text(_yaml.dump(data))

    movements = apply_season_results(
        {"TopperA": 10, "TopperB": 2}, n_games=10, tier="CH", top_n=4, path=path
    )

    # TopperA wins most → promoted; message uses the disambiguated name.
    assert "Promoted: Topper (alice) → PRM" in movements
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_leaderboard.py::test_apply_season_results_movement_uses_disambiguated_name -v`
Expected: FAIL — movement reads `Promoted: Topper → PRM` (no suffix)

- [ ] **Step 3: Wire in the helper**

In `game/components/leaderboard.py`, inside `apply_season_results`, change:

```python
    def _display(name: str) -> str:
        return data["players"][name].get("display_name", name)
```

to:

```python
    display_names = build_display_names(data["players"])

    def _display(name: str) -> str:
        return display_names.get(name, name)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/test_leaderboard.py::test_apply_season_results_movement_uses_disambiguated_name -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add game/components/leaderboard.py tests/test_leaderboard.py
git commit -m "feat(leaderboard): disambiguate names in promotion/relegation messages"
```

---

### Task 3: Wire helper into season summary + README rendering

**Files:**

- Modify: `.github/scripts/run_season.py` (`_standings_table`, `_write_summary`, `_update_readme`)
- Test: `tests/test_run_season.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_run_season.py`:

```python
def _load_run_season():
    """Import run_season.py as a module (main() is guarded, so this is side-effect free)."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("run_season", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_summary_disambiguates_duplicate_names(tmp_path):
    rs = _load_run_season()
    lb_path = tmp_path / "lb.yaml"
    summary = tmp_path / "summary.md"
    data = {
        "total_runs": 1,
        "players": {
            "TopperA": {
                "display_name": "Topper",
                "github_username": "alice",
                "tier": "PRM",
                "tier_stats": {"PRM": {"wins": 5, "games": 10, "win_pct": 50.0}},
            },
            "TopperB": {
                "display_name": "Topper",
                "github_username": "bob",
                "tier": "PRM",
                "tier_stats": {"PRM": {"wins": 3, "games": 10, "win_pct": 30.0}},
            },
            "Solo": {
                "display_name": "Solo",
                "github_username": "",
                "tier": "PRM",
                "tier_stats": {"PRM": {"wins": 1, "games": 10, "win_pct": 10.0}},
            },
        },
    }
    lb_path.write_text(yaml.dump(data))

    rs._write_summary(str(summary), {}, [], 10, str(lb_path))
    text = summary.read_text()

    assert "Topper (alice)" in text
    assert "Topper (bob)" in text
    assert "Solo (" not in text  # unique name stays bare


def test_readme_disambiguates_duplicate_names(tmp_path):
    rs = _load_run_season()
    lb_path = tmp_path / "lb.yaml"
    readme = tmp_path / "README.md"
    readme.write_text(
        "intro\n"
        "<!-- prettier-ignore-start -->\n"
        "<!-- leaderboard-start -->\n"
        "OLD\n"
        "<!-- leaderboard-end -->\n"
        "<!-- prettier-ignore-end -->\n"
        "footer\n"
    )
    data = {
        "players": {
            "TopperA": {
                "display_name": "Topper",
                "github_username": "alice",
                "tier": "PRM",
                "tier_stats": {"PRM": {"win_pct": 50.0}},
            },
            "TopperB": {
                "display_name": "Topper",
                "github_username": "bob",
                "tier": "PRM",
                "tier_stats": {"PRM": {"win_pct": 30.0}},
            },
        },
    }
    lb_path.write_text(yaml.dump(data))

    rs._update_readme(str(readme), str(lb_path))
    text = readme.read_text()

    assert "Topper (alice)" in text
    assert "Topper (bob)" in text
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_run_season.py -k disambiguates -v`
Expected: FAIL — both "Topper (alice)" / "Topper (bob)" missing (current code renders "Topper" twice)

- [ ] **Step 3: Update `_standings_table` to take the map**

In `.github/scripts/run_season.py`, change the signature:

```python
def _standings_table(tier_players: list[tuple[str, dict]], tier: str) -> list[str]:
```

to:

```python
def _standings_table(
    tier_players: list[tuple[str, dict]], tier: str, display_names: dict[str, str]
) -> list[str]:
```

and inside its row loop change:

```python
        display = p.get("display_name", name)
```

to:

```python
        display = display_names.get(name, name)
```

- [ ] **Step 4: Update `_write_summary` to build and thread the map**

In `_write_summary`, change:

```python
    data = _load_lb(lb_path)
    players = data.get("players", {})
```

to:

```python
    from game.components.leaderboard import build_display_names

    data = _load_lb(lb_path)
    players = data.get("players", {})
    display_names = build_display_names(players)
```

Then update the four uses:

1. Standings call — change `_standings_table(tier_players, tier)` to `_standings_table(tier_players, tier, display_names)`.
2. Inactive list — change `", ".join(p.get("display_name", n) for n, p in inactive_players)` to `", ".join(display_names.get(n, n) for n, _ in inactive_players)`.
3. Game-results table row — change `display = p.get("display_name", class_name)` to `display = display_names.get(class_name, class_name)`.
4. Movements loop — change `display = p.get("display_name", class_name)` to `display = display_names.get(class_name, class_name)`.

- [ ] **Step 5: Update `_update_readme` to build and thread the map**

In `_update_readme`, change:

```python
    data = _load_lb(lb_path)
    players = data.get("players", {})
```

to:

```python
    from game.components.leaderboard import build_display_names

    data = _load_lb(lb_path)
    players = data.get("players", {})
    display_names = build_display_names(players)
```

Then change both `_standings_table(...)` calls:

- `_standings_table(tier_players, tier)` → `_standings_table(tier_players, tier, display_names)`
- `_standings_table(inactive_players, "inactive")` → `_standings_table(inactive_players, "inactive", display_names)`

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run pytest tests/test_run_season.py -k disambiguates -v`
Expected: PASS (2 tests)

- [ ] **Step 7: Commit**

```bash
git add .github/scripts/run_season.py tests/test_run_season.py
git commit -m "feat(scripts): disambiguate duplicate names in summary and README rendering"
```

---

### Task 4: Regression guard on real data + full suite

**Files:**

- Test: `tests/test_leaderboard.py` (append)

- [ ] **Step 1: Write the regression test**

Append to `tests/test_leaderboard.py`:

```python
def test_build_display_names_no_op_on_current_leaderboard():
    """Every current display name is unique, so the helper adds no suffixes."""
    import yaml as _yaml
    from pathlib import Path

    from game.components.leaderboard import build_display_names

    repo_root = Path(__file__).parent.parent
    data = _yaml.safe_load((repo_root / "leaderboard.yaml").read_text())
    players = data["players"]

    result = build_display_names(players)
    for cn, p in players.items():
        assert result[cn] == p.get("display_name", cn)  # bare, no suffix added
```

- [ ] **Step 2: Run the regression test**

Run: `uv run pytest tests/test_leaderboard.py::test_build_display_names_no_op_on_current_leaderboard -v`
Expected: PASS (current leaderboard has all-unique names)

- [ ] **Step 3: Run the full suite**

Run: `uv run pytest tests/ -q`
Expected: PASS (all tests, including the new ones)

- [ ] **Step 4: Commit**

```bash
git add tests/test_leaderboard.py
git commit -m "test(leaderboard): assert disambiguation is a no-op on current data"
```

---

## Self-Review

**Spec coverage:**

- Global collision scope → Task 1 helper computes over the whole `players` dict. ✓
- Username-unique-else-class rule (covers empty + same-author) → Task 1 + tests for all four table rows. ✓
- Shared helper in `game/components/leaderboard.py` → Task 1. ✓
- All render sites → Task 2 (movements) + Task 3 (`_standings_table` shared across summary/README standings + inactive, plus summary's inactive list/game-results/movements). ✓ (Expanded beyond the spec's site list because `_standings_table` is shared by `_update_readme` too — same intent, more complete.)
- No schema change → only render-time reads; no writes to `leaderboard.yaml`. ✓
- No-op on current data + regression test → Task 4. ✓

**Placeholder scan:** none — every step has concrete code/commands.

**Type consistency:** `build_display_names(players: dict) -> dict[str, str]` defined in Task 1; consumed by `display_names.get(class_name, class_name)` in Tasks 2–3. `_standings_table(tier_players, tier, display_names)` signature defined in Task 3 Step 3 and called with three args in Steps 4–5. Consistent.
