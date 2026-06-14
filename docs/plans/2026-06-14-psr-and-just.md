# PSR + just — v1.0.0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship v1.0.0 by adding `next_tournament_monday()` to season_utils, wiring PSR + release.yml for automated releases, and creating a Justfile with local dev recipes.

**Architecture:** Six atomic commits on a feature branch. Season_utils gains four date-utility functions (moved from reset_season.py + one new). `.commitlintrc.mjs` gains the `doh` escape-hatch type. A `Justfile` at the repo root provides `develop`, `pytest`, `lint`, `simulate-season`, and `simulate-tournament`. A new `release.yml` workflow runs PSR on every push to main. The `feat!:` commit on release.yml triggers PSR to bump to v1.0.0.

**Tech Stack:** Python 3.11+, pytest, python-semantic-release, just, uv, PyYAML

**Spec:** `docs/specs/2026-06-14-psr-and-just-design.md`

---

## Pre-conditions

All `.semrel/` templates and the `[tool.semantic_release]` block in `pyproject.toml` are **already committed on `main`** (shipped with v0.9.1). No copy or setup step needed — the worktree will have them on checkout.

The branch for this work: `feat/psr-and-just` (new, branched from main).

---

## File Structure

| Action | Path                              | Responsibility                                                                    |
| ------ | --------------------------------- | --------------------------------------------------------------------------------- |
| Modify | `.github/scripts/season_utils.py` | Add `_today`, `current_quarter`, `is_tournament_monday`, `next_tournament_monday` |
| Modify | `tests/test_season_utils.py`      | Add 3 tests for `next_tournament_monday`                                          |
| Modify | `.github/scripts/reset_season.py` | Remove the 3 moved functions; extend `from season_utils import`                   |
| Modify | `.commitlintrc.mjs`               | Add `"doh"` to type-enum after `"player"`                                         |
| Create | `Justfile`                        | Local dev recipes                                                                 |
| Create | `.github/workflows/release.yml`   | PSR automation on push to main                                                    |

---

## Task 1: Extend season_utils.py with date utilities

**Files:**

- Modify: `.github/scripts/season_utils.py`
- Modify: `tests/test_season_utils.py`

- [ ] **Step 1: Write the 3 failing tests for `next_tournament_monday`**

Append to `tests/test_season_utils.py` (after the existing `test_save_lb_round_trips` at line 76):

```python


# --- next_tournament_monday ---


def test_next_tournament_monday_on_tournament_day():
    mod = _load()
    # 2026-07-06 is the first Monday of Q3 — should return itself
    result = mod.next_tournament_monday(date(2026, 7, 6))
    assert result == date(2026, 7, 6)


def test_next_tournament_monday_before_quarter():
    mod = _load()
    # Mid-June: next tournament Monday is the first Monday of Q3
    result = mod.next_tournament_monday(date(2026, 6, 15))
    assert result == date(2026, 7, 6)


def test_next_tournament_monday_day_after():
    mod = _load()
    # 2026-07-07 (Tuesday after Q3 tournament): next is Q4, first Monday of October
    result = mod.next_tournament_monday(date(2026, 7, 7))
    assert result == date(2026, 10, 5)
```

Also add `from datetime import date` at the top of `tests/test_season_utils.py` (after `from pathlib import Path`):

```python
from datetime import date
```

- [ ] **Step 2: Run the 3 new tests to confirm they fail**

```bash
uv run pytest tests/test_season_utils.py -k "next_tournament" -v
```

Expected: 3 failures with `AttributeError: module 'season_utils' has no attribute 'next_tournament_monday'`.

- [ ] **Step 3: Implement the 4 date utility functions in `season_utils.py`**

Replace the current imports block in `.github/scripts/season_utils.py`:

```python
import os
from datetime import datetime, timezone
```

With:

```python
import os
from datetime import date, datetime, timedelta, timezone
```

Then append these 4 functions after `_save_lb` (at the end of the file):

```python

def _today() -> date:
    raw = os.environ.get("TODAY")
    if not raw:
        return date.today()
    try:
        return date.fromisoformat(raw)
    except ValueError:
        raise ValueError(f"TODAY env var must be YYYY-MM-DD, got: {raw!r}") from None


def current_quarter(today: date | None = None) -> str:
    """Return e.g. '2026-Q3' for the quarter containing today."""
    d = today or _today()
    q = (d.month - 1) // 3 + 1
    return f"{d.year}-Q{q}"


def is_tournament_monday(today: date | None = None) -> bool:
    """Return True if today is the first Monday of a new quarter."""
    d = today or _today()
    if d.weekday() != 0:  # 0 = Monday
        return False
    return d.month in (1, 4, 7, 10) and d.day <= 7


def next_tournament_monday(today: date | None = None) -> date:
    """Return the next date that is a tournament Monday (on or after today)."""
    d = today or _today()
    for i in range(100):
        candidate = d + timedelta(days=i)
        if is_tournament_monday(candidate):
            return candidate
    raise ValueError("No tournament Monday found in next 100 days")
```

- [ ] **Step 4: Run the full test suite**

```bash
uv run pytest -v
```

Expected: all tests pass (existing 6 season_utils tests + 3 new + all reset_season tests).

- [ ] **Step 5: Commit**

```bash
git add .github/scripts/season_utils.py tests/test_season_utils.py
git commit -m "$(cat <<'EOF'
feat(scripts): add date utilities and next_tournament_monday to season_utils

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Migrate date functions from reset_season.py

**Files:**

- Modify: `.github/scripts/reset_season.py` (lines 25, 35, 40–67)

The existing tests in `test_reset_season.py` do **not** need changes — they test via the `reset_season` module, and after this task the module re-exports the functions via `from season_utils import`.

- [ ] **Step 1: Update `reset_season.py` imports and remove the 3 moved functions**

In `.github/scripts/reset_season.py`:

**Remove line 25 entirely** (no longer needed after the move):

```python
from datetime import date, datetime, timezone
```

**Replace line 35** (`from season_utils import _load_lb, _save_lb`) with:

```python
from season_utils import _load_lb, _save_lb, _today, current_quarter, is_tournament_monday  # noqa: E402
```

**Remove lines 40–68** — the three function definitions and their docstrings/comments:

```python
def _today() -> date:
    raw = os.environ.get("TODAY")
    if not raw:
        return date.today()
    try:
        return date.fromisoformat(raw)
    except ValueError:
        raise ValueError(f"TODAY env var must be YYYY-MM-DD, got: {raw!r}") from None


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def current_quarter(today: date | None = None) -> str:
    """Return e.g. '2026-Q3' for the quarter containing today."""
    d = today or _today()
    q = (d.month - 1) // 3 + 1
    return f"{d.year}-Q{q}"


def is_tournament_monday(today: date | None = None) -> bool:
    """Return True if today is the first Monday of a new quarter."""
    d = today or _today()
    if d.weekday() != 0:  # 0 = Monday
        return False
    return d.month in (1, 4, 7, 10) and d.day <= 7
```

After the edit, the file should have the `from season_utils import ...` line immediately after the `sys.path` bootstrap block, followed by the `_DRY_RUN` constant, followed by `form_pools`.

- [ ] **Step 2: Run the full test suite**

```bash
uv run pytest -v
```

Expected: all tests pass. The `test_reset_season.py` tests for `_today`, `current_quarter`, and `is_tournament_monday` still pass because `reset_season` now imports and re-exports them from `season_utils`.

- [ ] **Step 3: Commit**

```bash
git add .github/scripts/reset_season.py
git commit -m "$(cat <<'EOF'
refactor(scripts): migrate date functions from reset_season to season_utils

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Add `doh` to commitlint

**Files:**

- Modify: `.commitlintrc.mjs` (line 38 — after `"player"`)

- [ ] **Step 1: Add `doh` to the type-enum**

In `.commitlintrc.mjs`, the current end of the type-enum array is:

```js
        "player", // adding or updating a player strategy (players/); ignored by semantic-release
      ],
```

Replace it with:

```js
        "player", // adding or updating a player strategy (players/); ignored by semantic-release
        "doh", // escape hatch — never bumps version, never appears in changelog
      ],
```

- [ ] **Step 2: Verify commitlint accepts a `doh:` message**

```bash
echo "doh: oops, noise commit" | npx --no-install commitlint
```

Expected: exit 0 (no errors). If `npx --no-install` fails, try `npx commitlint --edit` or just verify the syntax by inspection.

- [ ] **Step 3: Commit**

```bash
git add .commitlintrc.mjs
git commit -m "$(cat <<'EOF'
chore: add doh type to commitlint

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Create Justfile

**Files:**

- Create: `Justfile` (repo root)

- [ ] **Step 1: Create the Justfile**

Create `Justfile` at the repo root with this exact content:

```just
# Install/upgrade dev dependencies and tools
develop:
    uv sync --dev
    uv tool install --upgrade wrkflw

# Run the full test suite
pytest:
    uv run pytest -v

# Lint and format check
lint:
    uv run ruff check .
    uv run ruff format --check .

# Simulate a season run (dry run). Optional date arg defaults to today.
# Usage: just simulate-season
#        just simulate-season 2026-07-07
simulate-season date=`date +%Y-%m-%d`:
    TODAY={{date}} DRY_RUN=1 uv run python .github/scripts/run_season.py

# Simulate the next tournament (dry run). Finds the next quarterly Monday automatically.
simulate-tournament:
    uv run python -c "\
import subprocess, os, sys; \
sys.path.insert(0, '.github/scripts'); \
from season_utils import next_tournament_monday; \
env = {**os.environ, 'TODAY': str(next_tournament_monday()), 'DRY_RUN': '1'}; \
subprocess.run(['uv', 'run', 'python', '.github/scripts/reset_season.py'], env=env, check=True)"
```

- [ ] **Step 2: Verify the Justfile works** (requires `just` installed; install with `brew install just` on macOS)

```bash
just pytest
```

Expected: runs `uv run pytest -v` and all tests pass.

```bash
just lint
```

Expected: `uv run ruff check .` and `uv run ruff format --check .` both pass with no issues.

```bash
just simulate-season
```

Expected: runs `run_season.py` in dry-run mode using today's date; exits 0 (DRY_RUN suppresses file writes).

- [ ] **Step 3: Commit**

```bash
git add Justfile
git commit -m "$(cat <<'EOF'
feat: add Justfile with develop, pytest, lint, and simulate recipes

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Create release.yml

**Files:**

- Create: `.github/workflows/release.yml`

This workflow runs PSR on every push to `main`. It uses `LEADERBOARD_PAT` (the existing admin token already used by other workflows) so PSR can push the version-bump commit and tag past branch protection. The `feat!:` commit message triggers PSR to create v1.0.0.

- [ ] **Step 1: Create `.github/workflows/release.yml`**

```yaml
name: release

on:
  push:
    branches: [main]

permissions:
  contents: write

jobs:
  release:
    runs-on: ubuntu-latest
    concurrency: release
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
          token: ${{ secrets.LEADERBOARD_PAT }}

      - uses: astral-sh/setup-uv@v5

      - name: Install python-semantic-release
        run: uv tool install python-semantic-release

      - name: Run semantic-release
        run: semantic-release version
        env:
          GH_TOKEN: ${{ secrets.LEADERBOARD_PAT }}
```

- [ ] **Step 2: Verify no syntax errors**

```bash
uv run python -c "import yaml; yaml.safe_load(open('.github/workflows/release.yml'))"
```

Expected: exits 0 silently.

- [ ] **Step 3: Commit with `feat!:` to trigger a major version bump**

This commit is what signals PSR to create v1.0.0 when the PR merges. The `feat!:` suffix (or `BREAKING CHANGE:` footer) is required.

```bash
git add .github/workflows/release.yml
git commit -m "$(cat <<'EOF'
feat!: automate releases with python-semantic-release

BREAKING CHANGE: Releases are now created automatically by PSR on push to
main. The previous manual git-tag-and-push workflow is superseded.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Push branch and open PR

- [ ] **Step 1: Run the full test suite one final time**

```bash
uv run pytest -v
```

Expected: all tests pass (9 season_utils + all reset_season + all run_season + all example tests).

- [ ] **Step 2: Stage untracked plan docs and commit**

The `docs/superpowers/` directory is untracked and should be included in the PR.

```bash
git add docs/superpowers/
git commit -m "$(cat <<'EOF'
docs: add implementation plans for season_utils and psr-and-just

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 3: Push the branch**

```bash
git push -u origin feat/psr-and-just
```

- [ ] **Step 4: Open PR**

```bash
gh pr create \
  --title "feat!: PSR + just — automated releases and local dev recipes (v1.0.0)" \
  --body "$(cat <<'EOF'
## Summary

- Extends `season_utils.py` with `_today`, `current_quarter`, `is_tournament_monday` (moved from `reset_season.py`) and new `next_tournament_monday()` — returns the first Monday on/after the next quarterly boundary
- Removes the three date functions from `reset_season.py`; imports them from `season_utils` instead; removes now-unused `from datetime import date, datetime, timezone`
- Adds `doh` type to `.commitlintrc.mjs` — escape hatch that never bumps the version and never appears in the CHANGELOG
- Adds `Justfile` at repo root with `develop`, `pytest`, `lint`, `simulate-season`, and `simulate-tournament` recipes
- Adds `.github/workflows/release.yml` — PSR runs on every push to `main`, bumps version, regenerates CHANGELOG, creates GitHub Release automatically

## Test plan

- [ ] `uv run pytest -v` passes (all tests green, including 3 new `next_tournament_monday` tests)
- [ ] `just pytest` runs the same suite via the Justfile
- [ ] `just simulate-tournament` resolves the next tournament Monday and runs `reset_season.py` in dry-run mode
- [ ] After merge, the `release` workflow creates a v1.0.0 GitHub Release automatically

🤖 Co-Authored with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Verification checklist (post-merge)

- `release` workflow runs on the merge commit
- PSR detects `feat!:` and bumps from `0.9.1` → `1.0.0`
- `pyproject.toml` version is updated to `1.0.0` by PSR
- CHANGELOG.md is regenerated with a `1.0.0` section
- GitHub Release `v1.0.0` is created with the release notes body
