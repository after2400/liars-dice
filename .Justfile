# Just runs the first target if no arguments are provided, so we set this to list all targets for safety.
_default:
    @just --list

# Install/upgrade dev dependencies and tools (maintainers: also `brew install wrkflw`)
[group('development')]
develop:
    uv sync --dev
    uv tool install pre-commit
    pre-commit install --hook-type commit-msg
    pre-commit install

# Run tests with optional path args (e.g. just pytest tests/test_main.py). No args = player_tests/.
[group('quality')]
pytest *args:
    uv run pytest {{args}} -v

# Run player tests (local sandbox — player_tests/ is gitignored)
[group('quality')]
pytest-players:
    uv run pytest player_tests/ -v; s=$?; [ $s -eq 5 ] && exit 0 || exit $s

# Run engine and integration tests (admin/engine PRs only)
[group('quality')]
pytest-all:
    uv run pytest tests/ examples/tests/ -v

# Lint and format check
[group('quality')]
lint:
    uv run ruff check .
    uv run ruff format --check .

# Register a player locally (dry run — no GitHub API calls).
# Usage: just register-player players/foo.py your-github-username
[group('algorithms')]
register-player file username:
    PLAYER_FILE={{file}} GITHUB_USERNAME={{username}} DRY_RUN=1 uv run python .github/scripts/register_player.py

# Check a player file against the exact validator the registration CI runs.
# Exits 0 if it would be accepted, or 1 listing why it would be rejected — run
# this before opening a PR. No GitHub calls, no leaderboard changes.
# Usage: just validate-player players/foo.py
[group('algorithms')]
validate-player file:
    uv run python -m game.validate {{file}}

# Validate a player file and, only if it passes, register it locally (dry run).
# One-step wrapper over validate-player + register-player; if validation fails,
# registration never runs.
# Usage: just add-player players/foo.py your-github-username
[group('algorithms')]
add-player file username: (validate-player file) (register-player file username)

# Simulate a season run (dry run). Optional date and extra args.
# Usage: just simulate-season
#        just simulate-season 2026-07-13
#        just simulate-season 2026-07-13 --tui
[group('algorithms')]
simulate-season *ARGS:
    DRY_RUN=1 uv run python -m game.simulation.season {{ARGS}}

# Simulate the next tournament (dry run). Finds the next quarterly Monday automatically.
# Usage: just simulate-tournament
#        just simulate-tournament --tui
[group('algorithms')]
simulate-tournament *ARGS:
    DRY_RUN=1 uv run python -m game.simulation.tournament {{ARGS}}

# Simulate a full quarter: tournament + all regular Mondays. Writes sim-YYYY-QN.md.
# Usage: just simulate-quarter
#        just simulate-quarter --start 2026-07-06
#        just simulate-quarter --start 2026-07-06 --n-games 500
#        just simulate-quarter --n-games 500 --tui
[group('algorithms')]
simulate-quarter *ARGS:
    uv run python -m game.simulation.quarter {{ARGS}}

# Reset files written by simulate-* recipes. Optional path for worktrees.
# Usage: just clean
#        just clean .claude/worktrees/my-worktree
[group('algorithms')]
clean path='.':
    git -C {{path}} checkout -- leaderboard.yaml
    rm -f {{path}}/season_summary.md
