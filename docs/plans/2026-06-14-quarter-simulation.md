# Quarter Simulation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `game/simulation/quarter.py` — a script that simulates a full quarter (tournament Monday + all subsequent regular Mondays) using `DRY_RUN=true`, streaming output to console and writing a plain-Markdown report.

**Architecture:** Move `season_utils.py` from `.github/scripts/` into the `game` package as `game/season/utils.py`, update the two callers (`reset_season.py`, `run_season.py`) to import from there, then build the simulation script in `game/simulation/quarter.py`. The simulation shells out to `reset_season.py` / `run_season.py` via subprocess with `TODAY` and `DRY_RUN=true` set, matching exactly what CI does.

**Tech Stack:** Python 3.11, `uv run`, PyYAML, `argparse`, `subprocess.Popen` (line-by-line streaming)

---

## File Map

| Action | Path                                                        |
| ------ | ----------------------------------------------------------- |
| Create | `game/season/__init__.py`                                   |
| Move   | `.github/scripts/season_utils.py` → `game/season/utils.py`  |
| Modify | `.github/scripts/reset_season.py` — update import           |
| Modify | `.github/scripts/run_season.py` — update import             |
| Modify | `tests/test_season_utils.py` — update load path             |
| Modify | `tests/test_reset_season.py` — remove stale sys.path insert |
| Create | `game/simulation/__init__.py`                               |
| Create | `game/simulation/quarter.py`                                |
| Create | `tests/test_simulate_quarter.py`                            |

---

## Task 1: Move season_utils into the game package

**Files:**

- Create: `game/season/__init__.py`
- Move: `.github/scripts/season_utils.py` → `game/season/utils.py`
- Modify: `tests/test_season_utils.py`

- [ ] **Step 1: Create the season package and move the file**

```bash
mkdir -p game/season
touch game/season/__init__.py
git mv .github/scripts/season_utils.py game/season/utils.py
```

- [ ] **Step 2: Update test_season_utils.py to import directly**

The existing test uses `importlib.util` to load from a file path. Replace the whole `_load()` helper and its usages with a direct import. Open `tests/test_season_utils.py` and replace from the top through the first test:

```python
"""Tests for game/season/utils.py shared utilities."""

from datetime import date
from pathlib import Path

import yaml

from game.season.utils import (
    _load_lb,
    _save_lb,
    current_quarter,
    is_tournament_monday,
    next_tournament_monday,
)

REPO_ROOT = Path(__file__).parent.parent
```

Then replace every `mod._load_lb(` with `_load_lb(`, `mod._save_lb(` with `_save_lb(`, `mod.current_quarter(` with `current_quarter(`, `mod.is_tournament_monday(` with `is_tournament_monday(`, `mod.next_tournament_monday(` with `next_tournament_monday(`. Remove `mod = _load()` lines throughout.

- [ ] **Step 3: Run the season_utils tests**

```bash
uv run pytest tests/test_season_utils.py -v
```

Expected: all tests pass (same count as before the move).

- [ ] **Step 4: Commit**

```bash
git add game/season/__init__.py game/season/utils.py tests/test_season_utils.py
git commit -m "refactor: move season_utils into game/season/utils"
```

---

## Task 2: Update .github/scripts/ imports and their tests

**Files:**

- Modify: `.github/scripts/reset_season.py`
- Modify: `.github/scripts/run_season.py`
- Modify: `tests/test_reset_season.py`

- [ ] **Step 1: Update reset_season.py import**

In `.github/scripts/reset_season.py`, find the import block (currently around line 35):

```python
from season_utils import (  # noqa: E402
    _load_lb,
    _save_lb,
    _today,  # noqa: F401
    current_quarter,
    is_tournament_monday,  # noqa: F401
)
```

Replace with:

```python
from game.season.utils import (  # noqa: E402
    _load_lb,
    _save_lb,
    _today,  # noqa: F401
    current_quarter,
    is_tournament_monday,  # noqa: F401
)
```

- [ ] **Step 2: Update run_season.py import**

In `.github/scripts/run_season.py`, find (currently around line 35):

```python
from season_utils import _load_lb  # noqa: E402
```

Replace with:

```python
from game.season.utils import _load_lb  # noqa: E402
```

- [ ] **Step 3: Update test_reset_season.py — remove stale sys.path insert**

The `_load()` helper in `tests/test_reset_season.py` adds `.github/scripts/` to `sys.path` so that `reset_season.py`'s old `from season_utils import` could resolve. After the move, `reset_season.py` imports from `game.season.utils` instead, so the scripts-dir path is no longer needed for import resolution.

In `tests/test_reset_season.py`, find the `_load()` function:

```python
def _load():
    scripts_dir = str(REPO_ROOT / ".github" / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    spec = importlib.util.spec_from_file_location("reset_season", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
```

Replace with:

```python
def _load():
    spec = importlib.util.spec_from_file_location("reset_season", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
```

- [ ] **Step 4: Run the full test suite**

```bash
uv run pytest -v
```

Expected: all tests pass. If `test_reset_season.py` or `test_run_season.py` fail with an import error, check that `_REPO_ROOT` is on `sys.path` before `from game.season.utils import` runs. `reset_season.py` inserts it itself (line ~28), so this should be automatic.

- [ ] **Step 5: Commit**

```bash
git add .github/scripts/reset_season.py .github/scripts/run_season.py tests/test_reset_season.py
git commit -m "refactor: update .github/scripts to import from game.season.utils"
```

---

## Task 3: Implement compute_mondays()

**Files:**

- Create: `game/simulation/__init__.py`
- Create: `game/simulation/quarter.py` (skeleton + `compute_mondays`)
- Create: `tests/test_simulate_quarter.py`

- [ ] **Step 1: Create the simulation package**

```bash
touch game/simulation/__init__.py
```

- [ ] **Step 2: Write the failing tests**

Create `tests/test_simulate_quarter.py`:

```python
"""Tests for game/simulation/quarter.py."""

from datetime import date

import pytest


def test_compute_mondays_q3_2026():
    from game.simulation.quarter import compute_mondays

    result = compute_mondays(date(2026, 7, 6))
    assert len(result) == 13
    assert result[0] == (date(2026, 7, 6), "tournament")
    assert result[1] == (date(2026, 7, 13), "season")
    assert result[-1] == (date(2026, 9, 28), "season")


def test_compute_mondays_first_is_always_tournament():
    from game.simulation.quarter import compute_mondays

    result = compute_mondays(date(2026, 7, 6))
    assert result[0][1] == "tournament"
    for _, mode in result[1:]:
        assert mode == "season"


def test_compute_mondays_q4_2026():
    from game.simulation.quarter import compute_mondays

    result = compute_mondays(date(2026, 10, 5))
    assert result[0] == (date(2026, 10, 5), "tournament")
    assert result[-1] == (date(2026, 12, 28), "season")
    assert len(result) == 13


def test_compute_mondays_all_mondays():
    from game.simulation.quarter import compute_mondays

    result = compute_mondays(date(2026, 7, 6))
    for d, _ in result:
        assert d.weekday() == 0  # Monday
```

- [ ] **Step 3: Run to confirm failure**

```bash
uv run pytest tests/test_simulate_quarter.py -v
```

Expected: `ImportError` — `game.simulation.quarter` does not exist yet.

- [ ] **Step 4: Create quarter.py with compute_mondays()**

Create `game/simulation/quarter.py`:

```python
"""Quarter simulation — runs a full quarter locally with DRY_RUN=true."""

from __future__ import annotations

import argparse
import os
import subprocess
from datetime import date, timedelta
from io import StringIO
from pathlib import Path

from game.season.utils import current_quarter, next_tournament_monday

_REPO_ROOT = Path(__file__).parent.parent.parent
_SCRIPTS = _REPO_ROOT / ".github" / "scripts"


def compute_mondays(start: date) -> list[tuple[date, str]]:
    """Return [(date, mode), ...] for every Monday in the quarter starting at start.

    start must be a tournament Monday. The sequence runs up to (not including)
    the next tournament Monday.
    """
    end = next_tournament_monday(start + timedelta(days=1))
    mondays: list[tuple[date, str]] = []
    d = start
    while d < end:
        mode = "tournament" if d == start else "season"
        mondays.append((d, mode))
        d += timedelta(days=7)
    return mondays
```

- [ ] **Step 5: Run tests**

```bash
uv run pytest tests/test_simulate_quarter.py -v
```

Expected: all 4 tests pass.

- [ ] **Step 6: Commit**

```bash
git add game/simulation/__init__.py game/simulation/quarter.py tests/test_simulate_quarter.py
git commit -m "feat(simulation): add compute_mondays"
```

---

## Task 4: Implement run_step()

**Files:**

- Modify: `game/simulation/quarter.py`
- Modify: `tests/test_simulate_quarter.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_simulate_quarter.py`:

```python
def test_run_step_sets_dry_run(monkeypatch, tmp_path):
    from game.simulation.quarter import run_step

    calls = []

    class FakeProc:
        stdout = iter(["[dry-run] would post\n"])
        returncode = 0
        def wait(self): pass

    def fake_popen(cmd, **kwargs):
        calls.append(kwargs.get("env", {}))
        return FakeProc()

    monkeypatch.setattr("game.simulation.quarter.subprocess.Popen", fake_popen)
    run_step(date(2026, 7, 6), "tournament", n_games=50, lb_path="leaderboard.yaml")

    assert calls[0]["DRY_RUN"] == "true"


def test_run_step_sets_today(monkeypatch):
    from game.simulation.quarter import run_step

    calls = []

    class FakeProc:
        stdout = iter([])
        returncode = 0
        def wait(self): pass

    def fake_popen(cmd, **kwargs):
        calls.append(kwargs.get("env", {}))
        return FakeProc()

    monkeypatch.setattr("game.simulation.quarter.subprocess.Popen", fake_popen)
    run_step(date(2026, 7, 13), "season", n_games=50, lb_path="leaderboard.yaml")

    assert calls[0]["TODAY"] == "2026-07-13"


def test_run_step_calls_correct_script(monkeypatch):
    from game.simulation.quarter import run_step

    cmds = []

    class FakeProc:
        stdout = iter([])
        returncode = 0
        def wait(self): pass

    def fake_popen(cmd, **kwargs):
        cmds.append(cmd)
        return FakeProc()

    monkeypatch.setattr("game.simulation.quarter.subprocess.Popen", fake_popen)

    run_step(date(2026, 7, 6), "tournament", n_games=50, lb_path="leaderboard.yaml")
    assert "reset_season.py" in cmds[-1][-1]

    run_step(date(2026, 7, 13), "season", n_games=50, lb_path="leaderboard.yaml")
    assert "run_season.py" in cmds[-1][-1]


def test_run_step_returns_captured_output(monkeypatch):
    from game.simulation.quarter import run_step

    class FakeProc:
        stdout = iter(["line one\n", "line two\n"])
        returncode = 0
        def wait(self): pass

    monkeypatch.setattr(
        "game.simulation.quarter.subprocess.Popen",
        lambda *a, **kw: FakeProc(),
    )

    output = run_step(date(2026, 7, 6), "tournament", n_games=50, lb_path="leaderboard.yaml")
    assert "line one" in output
    assert "line two" in output
```

- [ ] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/test_simulate_quarter.py::test_run_step_sets_dry_run -v
```

Expected: `ImportError` or `AttributeError` — `run_step` not defined yet.

- [ ] **Step 3: Implement run_step()**

Add to `game/simulation/quarter.py` after `compute_mondays`:

```python
def run_step(
    step_date: date,
    mode: str,
    n_games: int,
    lb_path: str,
) -> str:
    """Run one Monday step via subprocess. Always sets DRY_RUN=true.

    Streams stdout+stderr to console line-by-line while accumulating for return.
    """
    script = _SCRIPTS / ("reset_season.py" if mode == "tournament" else "run_season.py")
    env = {
        **os.environ,
        "TODAY": step_date.isoformat(),
        "DRY_RUN": "true",
        "N_GAMES": str(n_games),
        "LEADERBOARD_PATH": lb_path,
    }
    proc = subprocess.Popen(
        ["uv", "run", "python", str(script)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
        cwd=str(_REPO_ROOT),
    )
    buf = StringIO()
    for line in proc.stdout:
        print(line, end="", flush=True)
        buf.write(line)
    proc.wait()
    return buf.getvalue()
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_simulate_quarter.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add game/simulation/quarter.py tests/test_simulate_quarter.py
git commit -m "feat(simulation): add run_step"
```

---

## Task 5: Implement write_report()

**Files:**

- Modify: `game/simulation/quarter.py`
- Modify: `tests/test_simulate_quarter.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_simulate_quarter.py`:

```python
def test_write_report_contains_quarter_header(tmp_path):
    from game.simulation.quarter import write_report

    lb = tmp_path / "leaderboard.yaml"
    lb.write_text("players:\n  Diego:\n    tier: PRM\n    display_name: Diego\n    github_username: ''\n    tier_stats:\n      PRM:\n        wins: 100\n        games: 200\n        win_pct: 50.0\n")
    out = tmp_path / "report.md"

    steps = [
        {"date": date(2026, 7, 6), "mode": "tournament", "output": "[done] tournament\n"},
        {"date": date(2026, 7, 13), "mode": "season", "output": "[done] season\n"},
    ]
    write_report(steps, str(lb), out, n_games=50)

    text = out.read_text()
    assert "2026-Q3" in text


def test_write_report_contains_monday_sections(tmp_path):
    from game.simulation.quarter import write_report

    lb = tmp_path / "leaderboard.yaml"
    lb.write_text("players: {}\n")
    out = tmp_path / "report.md"

    steps = [
        {"date": date(2026, 7, 6), "mode": "tournament", "output": "tournament output\n"},
        {"date": date(2026, 7, 13), "mode": "season", "output": "season output\n"},
    ]
    write_report(steps, str(lb), out, n_games=50)

    text = out.read_text()
    assert "2026-07-06" in text
    assert "Tournament" in text
    assert "2026-07-13" in text
    assert "Week 1" in text
    assert "tournament output" in text
    assert "season output" in text


def test_write_report_contains_final_standings(tmp_path):
    from game.simulation.quarter import write_report

    lb = tmp_path / "leaderboard.yaml"
    lb.write_text(
        "players:\n"
        "  Diego:\n"
        "    tier: PRM\n"
        "    display_name: Diego\n"
        "    github_username: ''\n"
        "    tier_stats:\n"
        "      PRM:\n"
        "        wins: 100\n"
        "        games: 200\n"
        "        win_pct: 50.0\n"
    )
    out = tmp_path / "report.md"
    write_report([], str(lb), out, n_games=50)

    text = out.read_text()
    assert "Final Standings" in text
    assert "Premier" in text
    assert "Diego" in text
```

- [ ] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/test_simulate_quarter.py::test_write_report_contains_quarter_header -v
```

Expected: `ImportError` — `write_report` not defined yet.

- [ ] **Step 3: Implement write_report()**

Add to `game/simulation/quarter.py` after `run_step`:

```python
_TIER_LABEL = {"PRM": "Premier", "CH": "Championship", "L1": "League One"}


def write_report(
    steps: list[dict],
    lb_path: str,
    output_file: Path,
    n_games: int,
) -> None:
    """Write a plain-Markdown simulation report."""
    from game.components.leaderboard import build_display_names
    from game.season.utils import _load_lb

    data = _load_lb(lb_path)
    players = data.get("players", {})
    display_names = build_display_names(players)

    # Derive quarter from the first step date, or fall back to today.
    first_date = steps[0]["date"] if steps else date.today()
    quarter = current_quarter(first_date)

    lines: list[str] = [
        f"# Quarter Simulation: {quarter}",
        f"**Start:** {first_date} | **Mondays:** {len(steps)} | **Games/run:** {n_games}",
        "",
    ]

    for i, step in enumerate(steps):
        d = step["date"]
        mode = step["mode"]
        output = step["output"]

        if mode == "tournament":
            label = "Tournament"
        else:
            label = f"Week {i}"

        lines.append(f"## {d} — {label}")
        lines.append("")
        lines.append(output.rstrip())
        lines.append("")

    lines += ["---", "", "## Final Standings", ""]

    for tier, label in _TIER_LABEL.items():
        tier_players = [
            (n, p) for n, p in players.items() if p.get("tier") == tier
        ]
        tier_players.sort(
            key=lambda x: -x[1].get("tier_stats", {}).get(tier, {}).get("win_pct", 0.0)
        )
        lines.append(f"### {label}")
        if tier_players:
            lines.append(
                f"| Player | Win % in {tier} | Wins | Win % Total | Total Wins | Games |"
            )
            lines.append("|--------|----------------|------|-------------|------------|-------|")
            for name, p in tier_players:
                display = display_names.get(name, name)
                ts = p.get("tier_stats", {}).get(tier, {})
                all_ts = p.get("tier_stats", {}).values()
                total_wins = sum(t.get("wins", 0) for t in all_ts)
                total_games = sum(t.get("games", 0) for t in p.get("tier_stats", {}).values())
                total_pct = round(total_wins / total_games * 100, 1) if total_games else 0.0
                lines.append(
                    f"| {display} | {ts.get('win_pct', 0.0)} | {ts.get('wins', 0)} "
                    f"| {total_pct} | {total_wins} | {total_games} |"
                )
        else:
            lines.append(f"*No players currently in {label}.*")
        lines.append("")

    inactive = [n for n, p in players.items() if p.get("tier") == "inactive"]
    if inactive:
        inactive_names = ", ".join(display_names.get(n, n) for n in inactive)
        lines.append(f"*Inactive: {inactive_names}*")
        lines.append("")

    output_file.write_text("\n".join(lines))
    print(f"[done] Report written to {output_file}")
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_simulate_quarter.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add game/simulation/quarter.py tests/test_simulate_quarter.py
git commit -m "feat(simulation): add write_report"
```

---

## Task 6: Wire parse_args() and main()

**Files:**

- Modify: `game/simulation/quarter.py`
- Modify: `tests/test_simulate_quarter.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_simulate_quarter.py`:

```python
def test_parse_args_defaults(monkeypatch):
    from game.simulation.quarter import parse_args
    from game.season.utils import next_tournament_monday
    import sys

    monkeypatch.setattr(sys, "argv", ["quarter.py"])
    args = parse_args()

    assert args.n_games == int(os.environ.get("N_GAMES", "1000"))
    assert args.start == next_tournament_monday()
    assert args.output is None


def test_parse_args_start_override(monkeypatch):
    from game.simulation.quarter import parse_args
    import sys

    monkeypatch.setattr(sys, "argv", ["quarter.py", "--start", "2026-07-06"])
    args = parse_args()
    assert args.start == date(2026, 7, 6)


def test_parse_args_n_games_override(monkeypatch):
    from game.simulation.quarter import parse_args
    import sys

    monkeypatch.setattr(sys, "argv", ["quarter.py", "--n-games", "50"])
    args = parse_args()
    assert args.n_games == 50
```

Add `import os` to the top of `tests/test_simulate_quarter.py`.

- [ ] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/test_simulate_quarter.py::test_parse_args_defaults -v
```

Expected: `ImportError` — `parse_args` not defined yet.

- [ ] **Step 3: Implement parse_args() and main()**

Append to `game/simulation/quarter.py`:

```python
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Simulate a full quarter locally (DRY_RUN=true, no GitHub changes)."
    )
    parser.add_argument(
        "--start",
        type=lambda s: date.fromisoformat(s),
        default=next_tournament_monday(),
        help="Tournament Monday to start from (YYYY-MM-DD). Default: next upcoming.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Report output path. Default: sim-YYYY-QN.md in current directory.",
    )
    parser.add_argument(
        "--n-games",
        type=int,
        default=int(os.environ.get("N_GAMES", "1000")),
        help="Games per tier/pool per run. Default: N_GAMES env var or 1000.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    quarter = current_quarter(args.start)
    output_file = args.output or Path(f"sim-{quarter}.md")
    lb_path = os.environ.get("LEADERBOARD_PATH", "leaderboard.yaml")

    mondays = compute_mondays(args.start)
    print(f"[simulate] {quarter}: {len(mondays)} Mondays, {args.n_games} games/run")
    print(f"[simulate] leaderboard: {lb_path}")
    print(f"[simulate] report: {output_file}")
    print()

    steps: list[dict] = []
    for step_date, mode in mondays:
        label = "Tournament" if mode == "tournament" else "season"
        print(f"{'='*60}")
        print(f"[simulate] {step_date} — {label}")
        print(f"{'='*60}")
        output = run_step(step_date, mode, args.n_games, lb_path)
        steps.append({"date": step_date, "mode": mode, "output": output})
        print()

    write_report(steps, lb_path, output_file, args.n_games)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run all tests**

```bash
uv run pytest tests/test_simulate_quarter.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add game/simulation/quarter.py tests/test_simulate_quarter.py
git commit -m "feat(simulation): add parse_args and main — quarter simulation complete"
```

---

## Task 7: Full test suite and smoke test

**Files:** none new

- [ ] **Step 1: Run the full test suite**

```bash
uv run pytest -v
```

Expected: all tests pass including existing `test_reset_season.py`, `test_run_season.py`, `test_season_utils.py`.

- [ ] **Step 2: Smoke test with --n-games 10**

```bash
DRY_RUN=true uv run python -m game.simulation.quarter --n-games 10
```

Expected:

- Prints a header showing the quarter, Monday count, and report path
- Runs tournament step (prints `[dry-run]` lines, no GitHub calls)
- Runs 12 regular season steps
- Writes `sim-YYYY-QN.md` in the current directory
- Final line: `[done] Report written to sim-YYYY-QN.md`

Check the report file exists and has the right structure:

```bash
head -20 sim-*.md
```

Expected: starts with `# Quarter Simulation: YYYY-QN` and contains `## Final Standings`.

- [ ] **Step 3: Commit any fixups, then final check**

```bash
git status
uv run pytest -v
```

Expected: clean working tree (or only the report `.md` file untracked), all tests green.
