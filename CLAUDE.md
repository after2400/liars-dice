# liars-dice — Project Rules

## Repo overview

**What it is:** A Liar's Dice league system. Players are Python bots (`players/*.py`). Each Monday the CI runs games and updates standings. Quarterly, a tournament re-seeds everyone into tiers.

**Tiers (high → low):** PRM → CH → L1 → (inactive / DED). Capacity scales with player count (`tier_capacities()` in `game/components/leaderboard.py`).

**The quarter cycle:**

1. **Tournament Monday** (first Monday of Jan/Apr/Jul/Oct) — `reset_season.py`: zeros all `tier_stats`, runs pool games to rank everyone, calls `assign_placements()` to write new tiers into `leaderboard.yaml`, creates the quarter's GitHub tracking issue.
2. **Regular Mondays** — `run_season.py`: runs games per tier bottom-up (inactive → L1 → CH → PRM), applies promotions/relegations via `apply_season_results()` + `settle_relegations()`, updates README standings, posts a summary comment to the tracking issue.

**Single source of truth:** `leaderboard.yaml` — mutated in-place by every script. The tournament resets it; there is no separate per-quarter file.

**Key env vars:**
| Var | Default | Purpose |
|-----|---------|---------|
| `TODAY` | system date | Override the current date (YYYY-MM-DD) — used in `season_utils._today()` to mock time |
| `DRY_RUN` | false | Skip GitHub API calls (issue creation, comments, git push) but still run games locally |
| `N_GAMES` | 1000 | Games per tier/pool per run |
| `TOP_N` | 4 | League capacity per tier (PRM/CH) |
| `LEADERBOARD_PATH` | leaderboard.yaml | Path to the leaderboard file |

**Key scripts** (in `.github/scripts/` unless noted):

- `game/season/utils.py` — shared helpers: `_load_lb`, `_save_lb`, `_today()`, `is_tournament_monday()`, `next_tournament_monday()`, `current_quarter()`
- `reset_season.py` — quarterly tournament reset (idempotent via `tournament_state` in leaderboard)
- `run_season.py` — regular Monday season driver
- `register_player.py` — registers a new player bot into `leaderboard.yaml`
- `game/simulation/quarter.py` — simulate a full quarter locally (`uv run python -m game.simulation.quarter`)

## Python execution

**Always use `uv run python` — never bare `python3` or `python`.**

```bash
# correct
uv run python -m game ...
uv run python .github/scripts/register_player.py
just pytest

# wrong — do not use
python3 script.py
python -m game
pytest tests/
uv run pytest -v
```

This applies everywhere: shell commands, CI scripts, subagent prompts, code review suggestions. No exceptions.

## Testing

Two recipes — use the right one for the work:

```bash
# Player development (default) — runs player_tests/ only
just pytest

# Engine / admin PRs — runs tests/ and examples/tests/
just pytest-all
```

`player_tests/` is gitignored. Write bot tests there freely; they run locally but are never committed. When working on engine code, always use `just pytest-all` before committing — `just pytest` alone does not cover engine tests.

## Commits

Before writing a commit message, check:

- **`.commitlintrc.mjs`** — enforced `type-enum` and `scope-enum`. Types like `player` and `doh` are custom to this project. Scopes are optional but must be from the list when used.
- **`pyproject.toml` `[tool.semantic_release.commit_parser_options]`** — `minor_tags` and `patch_tags` control what bumps the version. `feat` → minor, `fix`/`perf` → patch. Everything else (`docs`, `chore`, `ci`, `player`, `doh`, etc.) does not bump.

## PR and commit attribution

All PRs must use `🤖 Co-Authored with [Claude Code](https://claude.com/claude-code)` in the body footer — not "Generated with". This project is a genuine collaboration.
