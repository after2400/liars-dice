"""Quarter simulation — runs a full quarter locally with DRY_RUN=true."""

from __future__ import annotations

from datetime import date, timedelta
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
