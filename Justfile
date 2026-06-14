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
    uv run python -c "import subprocess, os, sys; sys.path.insert(0, '.github/scripts'); from season_utils import next_tournament_monday; env = {**os.environ, 'TODAY': str(next_tournament_monday()), 'DRY_RUN': '1'}; subprocess.run(['uv', 'run', 'python', '.github/scripts/reset_season.py'], env=env, check=True)"
