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

# Simulate a season run (dry run). Optional date arg defaults to today.
# Usage: just simulate-season
#        just simulate-season 2026-07-07
[group('algorithms')]
simulate-season date=`date +%Y-%m-%d`:
    TODAY={{date}} DRY_RUN=1 uv run python .github/scripts/run_season.py

# Simulate the next tournament (dry run). Finds the next quarterly Monday automatically.
[group('algorithms')]
simulate-tournament:
    TODAY=$(uv run python -c "from game.season.utils import next_tournament_monday; print(next_tournament_monday())") DRY_RUN=1 uv run python .github/scripts/reset_season.py

# Simulate a full quarter: tournament + all regular Mondays. Writes sim-YYYY-QN.md.
# Usage: just simulate-quarter
#        just simulate-quarter 2026-07-06
#        just simulate-quarter 2026-07-06 500
[group('algorithms')]
simulate-quarter start='' n-games='':
    uv run python -m game.simulation.quarter \
        $([ -n "{{start}}" ] && echo "--start {{start}}") \
        $([ -n "{{n-games}}" ] && echo "--n-games {{n-games}}")

# Reset files written by simulate-* recipes. Optional path for worktrees.
# Usage: just clean
#        just clean .claude/worktrees/my-worktree
[group('algorithms')]
clean path='.':
    git -C {{path}} checkout -- leaderboard.yaml
    rm -f {{path}}/season_summary.md
