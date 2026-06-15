"""Quarter simulation — runs a full quarter locally with DRY_RUN=true."""

from __future__ import annotations

import os
import subprocess
from datetime import date, timedelta
from io import StringIO
from pathlib import Path

from game.season.utils import next_tournament_monday

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
