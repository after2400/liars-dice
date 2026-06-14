# PSR + just — v1.0.0 Design

## Overview

Introduce two developer-experience tools for the liars-dice project:

1. **python-semantic-release (PSR)** — automated version bumping, changelog generation, and GitHub
   release creation on every push to `main`.
2. **just** — a cross-platform task runner that replaces ad-hoc shell commands with documented,
   reproducible recipes.

These ship together as v1.0.0 because they form the complete release automation story: PSR provides
the automation, just provides the local workflow.

---

## 1. PSR Configuration

PSR is a **CI-only tool** — it is not in `pyproject.toml` dev dependencies and is never required
to run the game or tests locally. Developers who want to experiment with it locally can install it
with `uv tool install python-semantic-release`.

### pyproject.toml additions

Already written and validated locally (unstaged). The full block:

```toml
[tool.semantic_release]
version_toml = ["pyproject.toml:project.version"]
tag_format = "v{version}"

[tool.semantic_release.branches.main]
match = "main"
prerelease = false

[tool.semantic_release.commit_parser_options]
allowed_tags = ["feat", "fix", "perf", "refactor", "style", "test", "docs", "build", "ci", "chore", "revert", "player", "doh"]
minor_tags = ["feat"]
patch_tags = ["fix", "perf"]

[tool.semantic_release.changelog]
mode = "init"
template_dir = ".semrel"
exclude_commit_patterns = [
    "^doh(\\([^)]*\\))?!?:",
    "^player(\\([^)]*\\))?!?:",
    "^ci:.*\\[skip ci\\]",
]
```

**Key decisions:**

- `mode = "init"` — CHANGELOG.md is always fully regenerated, never patched. Ensures exclusion
  rules and template changes apply retroactively.
- `player:` and `doh:` excluded from changelog. `ci: … [skip ci]` excluded. All other types
  appear in the changelog under their emoji sections.
- `doh:` is in `allowed_tags` but not in `minor_tags` or `patch_tags` — it never triggers a
  version bump. Use it for commits that must not appear in the changelog and must not bump the
  version (e.g. reverting a bad commit mid-PR, squashing noise).

### Version bump rules

| Commit type                           | Example                                     | Bump  |
| ------------------------------------- | ------------------------------------------- | ----- |
| `feat!:` or `BREAKING CHANGE:` footer | `feat!: redesign scoring`                   | major |
| `feat:`                               | `feat: add player Finn`                     | minor |
| `fix:`, `perf:`                       | `fix: relegate correctly`                   | patch |
| Everything else                       | `chore:`, `docs:`, `ci:`, `player:`, `doh:` | none  |

### Changelog template (.semrel/)

Already written and validated locally (untracked). Files:

- `.semrel/CHANGELOG.md.j2` — top-level changelog template (PSR default, unmodified)
- `.semrel/.release_notes.md.j2` — GitHub Release body template (PSR default, unmodified)
- `.semrel/.components/changes.md.j2` — **custom** — renders emoji sections in sort order
- `.semrel/.components/macros.md.j2` — **custom** — adds `sort_tuples_by_order_dict` macro; rest
  are PSR defaults minus Jira-specific helpers
- All other `.semrel/.components/*.md.j2` — PSR defaults, unmodified

Emoji section order: 🚀 Major Release → ✨ Features → 🐛 Bug Fixes → ⚡ Performance →
♻️ Refactoring → 📝 Documentation → 🧪 Tests → 👷 CI/CD → 🔨 Build → 🔧 Chores →
⏪ Reverts → 💄 Code Style

The 🚀 Major Release section fires when any commit has `bump >= MAJOR (4)` — this covers both
`feat!:` (no BREAKING CHANGE footer needed) and commits with a `BREAKING CHANGE:` footer.
Major-bump commits are excluded from regular sections to avoid duplication.

---

## 2. release.yml Workflow

Triggered on every push to `main`. Uses `LEADERBOARD_PAT` (the existing admin token already used
by other workflows) so PSR can push the version-bump commit and tag past branch protection rules.

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

**`fetch-depth: 0`** — PSR must walk the full git history to compute the version from all tags.
Shallow clones produce incorrect version calculations.

**`concurrency: release`** — prevents two release jobs from racing on back-to-back pushes.

PSR's `version` command: bumps `pyproject.toml`, regenerates `CHANGELOG.md`, commits both,
creates the git tag, pushes, and creates the GitHub Release — all in one step.

---

## 3. commitlint additions

Add `doh` to the `type-enum` list in `.commitlintrc.mjs`:

```js
"doh", // escape hatch — never bumps version, never appears in changelog
```

No other commitlint changes required. `player:` is already in the enum (added in PR #26).

---

## 4. Justfile

A `Justfile` at the repo root. Requires `just` to be installed separately (documented in README).
Cross-platform via `uv run python` for any logic that can't be expressed as a plain shell command.

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
    uv run python -c "
import subprocess, os, sys
sys.path.insert(0, '.github/scripts')
from season_utils import next_tournament_monday
env = {**os.environ, 'TODAY': str(next_tournament_monday()), 'DRY_RUN': '1'}
subprocess.run(['uv', 'run', 'python', '.github/scripts/reset_season.py'], env=env, check=True)
"
```

**Notes:**

- `just develop` uses `--upgrade` so re-running updates wrkflw to the latest version rather than
  silently skipping if already installed.
- `simulate-season` uses Just's backtick default syntax for the date parameter — `date +%Y-%m-%d`
  evaluates at recipe invocation time, giving today's date.
- `simulate-tournament` uses an inline Python snippet (cross-platform via `uv run python`) to call
  `next_tournament_monday()` from `season_utils` and pass the result as `TODAY` to
  `reset_season.py`. No shebang needed, no extra script file.

---

## 5. season_utils: date utilities

Extend `.github/scripts/season_utils.py` with the date utility functions currently living in
`reset_season.py`, plus the new `next_tournament_monday()`.

### Functions to move from reset_season.py → season_utils.py

| Function                 | Signature                              | Notes                                               |
| ------------------------ | -------------------------------------- | --------------------------------------------------- |
| `_today()`               | `() -> date`                           | Reads `TODAY` env var; falls back to `date.today()` |
| `current_quarter()`      | `(today: date \| None = None) -> str`  | Returns e.g. `"2026-Q3"`                            |
| `is_tournament_monday()` | `(today: date \| None = None) -> bool` | First Monday of Jan/Apr/Jul/Oct                     |

### New function

```python
def next_tournament_monday(today: date | None = None) -> date:
    """Return the next date that is a tournament Monday (on or after today)."""
    d = today or _today()
    for i in range(100):
        candidate = d + timedelta(days=i)
        if is_tournament_monday(candidate):
            return candidate
    raise ValueError("No tournament Monday found in next 100 days")
```

The 100-day ceiling is a safety guard; the maximum gap between today and the next tournament
Monday is 97 days (a full quarter minus one day).

### reset_season.py updates

- Remove `_today()`, `current_quarter()`, `is_tournament_monday()` from `reset_season.py`
- Add `from season_utils import _today, current_quarter, is_tournament_monday` after the existing
  `from season_utils import _load_lb, _save_lb` line
- Existing tests in `test_reset_season.py` continue to test these functions via the module — no
  test changes required for the moves (the `_load()` helper already adds `.github/scripts/` to
  `sys.path`)

### New tests

Add to `tests/test_season_utils.py`:

```python
# --- next_tournament_monday ---

def test_next_tournament_monday_on_tournament_day():
    mod = _load()
    # 2026-07-06 is the first Monday of Q3 — should return itself
    result = mod.next_tournament_monday(date(2026, 7, 6))
    assert result == date(2026, 7, 6)

def test_next_tournament_monday_before_quarter():
    mod = _load()
    # Mid-June — next tournament Monday is 2026-07-06
    result = mod.next_tournament_monday(date(2026, 6, 15))
    assert result == date(2026, 7, 6)

def test_next_tournament_monday_day_after():
    mod = _load()
    # 2026-07-07 (Tuesday) — next is 2027-01-04
    result = mod.next_tournament_monday(date(2026, 7, 7))
    assert result == date(2027, 1, 4)
```

---

## 6. Files changed summary

| Action          | Path                                                                              |
| --------------- | --------------------------------------------------------------------------------- |
| Add (unstaged)  | `pyproject.toml` — PSR config block                                               |
| Add (untracked) | `.semrel/CHANGELOG.md.j2`                                                         |
| Add (untracked) | `.semrel/.release_notes.md.j2`                                                    |
| Add (untracked) | `.semrel/.components/changes.md.j2`                                               |
| Add (untracked) | `.semrel/.components/macros.md.j2`                                                |
| Add (untracked) | `.semrel/.components/changelog_header.md.j2`                                      |
| Add (untracked) | `.semrel/.components/changelog_init.md.j2`                                        |
| Add (untracked) | `.semrel/.components/changelog_update.md.j2`                                      |
| Add (untracked) | `.semrel/.components/versioned_changes.md.j2`                                     |
| Add (untracked) | `.semrel/.components/first_release.md.j2`                                         |
| Add (untracked) | `.semrel/.components/unreleased_changes.md.j2`                                    |
| Create          | `Justfile`                                                                        |
| Create          | `.github/workflows/release.yml`                                                   |
| Modify          | `.commitlintrc.mjs` — add `doh` type                                              |
| Modify          | `.github/scripts/season_utils.py` — add date utilities + `next_tournament_monday` |
| Modify          | `.github/scripts/reset_season.py` — remove moved functions, update import         |
| Modify          | `tests/test_season_utils.py` — add 3 tests for `next_tournament_monday`           |
