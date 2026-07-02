# liars-dice — Project Rules

## Repo overview

**What it is:** A Liar's Dice league system. Players are Python bots (`players/*.py`). Each Monday the CI runs games and updates standings. Quarterly, a tournament re-seeds everyone into tiers.

**Tiers (high → low):** PRM → CH → L1 → (inactive / DED). Capacity scales with player count (`tier_capacities()` in `game/components/leaderboard.py`).

**The quarter cycle:**

1. **Tournament Monday** (first Monday of Jan/Apr/Jul/Oct) — `reset_season.py`: zeros all `tier_stats`, runs pool games to rank everyone, calls `assign_placements()` to write new tiers into `leaderboard.yaml`, creates the quarter's GitHub tracking issue.
2. **Regular Mondays** — `run_season.py`: runs games per tier bottom-up (inactive → L1 → CH → PRM), applies promotions/relegations via `apply_season_results()` + `settle_relegations()`, updates README standings, posts a summary comment to the tracking issue.

**Single source of truth:** `leaderboard.yaml` — mutated in-place by every script. The tournament resets it; there is no separate per-quarter file.

**Key env vars:**

| Var                | Default          | Purpose                                                                                |
| ------------------ | ---------------- | -------------------------------------------------------------------------------------- |
| `TODAY`            | system date      | Override the current date (YYYY-MM-DD) — used in `season_utils._today()` to mock time  |
| `DRY_RUN`          | false            | Skip GitHub API calls (issue creation, comments, git push) but still run games locally |
| `N_GAMES`          | 1000             | Games per tier/pool per run                                                            |
| `TOP_N`            | 4                | League capacity per tier (PRM/CH)                                                      |
| `LEADERBOARD_PATH` | leaderboard.yaml | Path to the leaderboard file                                                           |

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
just pytest tests/test_main.py
just pytest-players
just pytest-all

# wrong — do not use
python3 script.py
python -m game
pytest tests/
uv run pytest -v
```

This applies everywhere: shell commands, CI scripts, subagent prompts, code review suggestions. No exceptions.

## Testing

Three recipes — use the right one for the work:

```bash
# Targeted run — pass any pytest path/node args
just pytest tests/test_main.py
just pytest tests/test_main.py::test_round_players_passed_when_declared

# Player development — runs player_tests/ only (exits 0 even if dir is empty)
just pytest-players

# Engine / admin PRs — runs tests/ and examples/tests/
just pytest-all
```

`player_tests/` is gitignored. Write bot tests there freely; they run locally but are never committed. When working on engine code, always use `just pytest-all` before committing — `just pytest-players` alone does not cover engine tests.

## Local simulation

Use these to test how a player performs before Monday's CI run. All simulation commands run with `DRY_RUN=true` — they modify `leaderboard.yaml` locally but make no GitHub API calls.

**Register a player locally first** (only needed if they're not yet in `leaderboard.yaml`):

```bash
just register-player players/foo.py your-login
```

**Single-step simulations:**

```bash
just simulate-tournament           # runs the next quarterly tournament (dry run)
just simulate-season 2026-07-13    # runs one regular Monday season step
```

**Full quarter simulation** — runs tournament + all regular Mondays in sequence, writes a Markdown report:

```bash
just simulate-quarter                        # next upcoming tournament Monday
just simulate-quarter 2026-07-06             # specific start date
just simulate-quarter 2026-07-06 500         # with custom game count
```

Outputs `sim-YYYY-QN.md` in the current directory. `leaderboard.yaml` is mutated in-place.

**Player performance instrumentation** — see how expensive your bot is (wall-clock time, CPU time, and optionally memory) before it hits CI. Works with all three simulation commands above; nothing to enable for timing, it's always on:

```bash
just simulate-season 2026-07-13                        # wall/CPU timing always included
just simulate-quarter --start 2026-07-06 --profile-memory   # add peak-memory-per-call tracking too
```

Each tier/pool's win-rate chart is followed by a `Player Performance` table, sorted slowest-first:

```
=== Player Performance — 100 games ===

  Player            Calls  TotalWall(s)  TotalCPU(s)  AvgWall(ms)  P95Wall(ms)  MaxWall(ms)  AvgCPU(ms)  MaxCPU(ms)
  ------------------------------------------------------------------------------------------------------------------
  MyBot              3196        30.885        30.236        9.664       23.008       56.012       9.460      38.479
```

- **Calls** — how many `algo()` invocations were timed, across every game in that tier/pool.
- **TotalWall(s) / TotalCPU(s)** — this bot's cumulative time across all those calls. If your bot's `TotalWall(s)` is a large share of the whole step's wall time, it's likely the bottleneck — but a long game (many rounds, hence many `Calls`) drives this up just as much as a slow bot does, so check `AvgWall(ms)` too before assuming your logic is the problem.
- **AvgWall(ms) / P95Wall(ms) / MaxWall(ms)** — per-call cost. A `MaxWall` far above `AvgWall`/`P95Wall` usually means an occasional expensive code path (e.g. a cache/table built lazily on first use, or a rare branch that does more work).
- **AvgCPU(ms) / MaxCPU(ms)** — CPU time, not wall time (`time.thread_time()`, isolated from any TUI rendering). Close to the wall numbers means your bot isn't blocked on I/O; a gap between them would be unusual for this engine.
- **AvgPeak(KB) / MaxPeak(KB)** (only with `--profile-memory`) — peak Python-level memory allocated _within a single call_, not cumulative. This has real overhead, so it's opt-in — use it when you suspect a specific bot is allocation-heavy, not as a default-on flag.

This is Phase 1: ephemeral, local-only — nothing here is written to `leaderboard.yaml` or shown in CI/README output.

**Clean up afterward:**

```bash
just clean                                          # restores leaderboard.yaml and removes season_summary.md
just clean .claude/worktrees/my-worktree            # clean a specific worktree
```

## Commits

Before writing a commit message, check:

- **`.commitlintrc.mjs`** — enforced `type-enum` and `scope-enum`. Types like `player` and `doh` are custom to this project. Scopes are optional but must be from the list when used.
- **`pyproject.toml` `[tool.semantic_release.commit_parser_options]`** — `minor_tags` and `patch_tags` control what bumps the version. `feat` → minor, `fix`/`perf` → patch. Everything else (`docs`, `chore`, `ci`, `player`, `doh`, etc.) does not bump.

## PR and commit attribution

All PRs must use `🤖 Co-Authored with [Claude Code](https://claude.com/claude-code)` in the body footer — not "Generated with". This project is a genuine collaboration.
