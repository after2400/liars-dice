# Just runs the first target if no arguments are provided, so we set this to list all targets for safety.
_default:
    @just --list

# Install/upgrade dev dependencies and tools
[group('development')]
develop:
    uv sync --dev
    uv tool install --upgrade wrkflw

# Run the full test suite
[group('quality')]
pytest:
    uv run pytest -v

# Lint and format check
[group('quality')]
lint:
    uv run ruff check .
    uv run ruff format --check .

# Simulate a season run (dry run). Optional date arg defaults to today.
# Usage: just simulate-season
#        just simulate-season 2026-07-07
[group('algorithms')]
simulate-season date=`date +%Y-%m-%d`:
    TODAY={{date}} DRY_RUN=1 uv run python .github/scripts/run_season.py

# Simulate the next tournament (dry run). Finds the next quarterly Monday automatically.
[group('algorithms')]
simulate-tournament:
    uv run python -c "import subprocess, os, sys; sys.path.insert(0, '.github/scripts'); from season_utils import next_tournament_monday; env = {**os.environ, 'TODAY': str(next_tournament_monday()), 'DRY_RUN': '1'}; subprocess.run(['uv', 'run', 'python', '.github/scripts/reset_season.py'], env=env, check=True)"

# Reset files written by simulate-season or simulate-tournament
[group('algorithms')]
clean:
    git checkout -- leaderboard.yaml
    rm -f season_summary.md
