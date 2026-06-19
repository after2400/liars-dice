# Contributing

**Looking to submit a player bot?** See the **[Wiki](https://github.com/after2400/liars-dice/wiki)** — rules, player API, and how to join.

This file covers local dev setup for working on the engine itself.

---

## Requirements

- [uv](https://docs.astral.sh/uv/) — Python package manager; also manages the Python version
- [just](https://just.systems/) — task runner (`brew install just` / `cargo install just` / [other](https://just.systems/man/en/packages.html))
- [Node.js](https://nodejs.org/) 18+ — required for the commitlint pre-commit hook

Run `just develop` once after cloning to install remaining tools and activate pre-commit hooks.

---

## Running Locally

Requires [`uv`](https://docs.astral.sh/uv/) and [`just`](https://just.systems/).

```bash
# one-time dev setup
just develop
```

### Tests and linting

```bash
just pytest tests/test_main.py   # targeted run — pass any path or node id
just pytest-players              # player sandbox tests (player_tests/ only)
just pytest-all                  # full engine + integration test suite
just lint                        # ruff check + format check
```

### Registering a player locally

Before simulating against a new bot, register it in `leaderboard.yaml`:

```bash
just register-player players/foo.py your-github-username
```

**Naming rule:** the class inside the file must match the filename exactly — `players/foo.py` must define `class Foo`.

This runs with `DRY_RUN=1`: it writes to `leaderboard.yaml` locally but makes no GitHub API calls. Use `just clean` afterward to restore it.

### Simulating runs

```bash
just simulate-season               # dry run with today's date
just simulate-season 2026-07-13    # dry run with a specific Monday date
just simulate-tournament           # dry run the next quarterly tournament

# Full quarter — runs tournament + all Mondays in sequence, writes sim-YYYY-QN.md
uv run python -m game.simulation.quarter
# --start 2026-07-06   tournament Monday to start from (default: next upcoming)
# --n-games 500        games per tier per run (default: 1000)

just clean                         # reset leaderboard.yaml and season_summary.md afterward
```

### Running games directly

```bash
uv run python -m game [N_GAMES] [TOP_N] [--tier TIER]
```

Examples:

```bash
uv run python -m game              # 1 game, every player file in players/
uv run python -m game 100 4        # 100 games, all players
uv run python -m game 50 4 --tier PRM   # 50 games, PRM players only
```
