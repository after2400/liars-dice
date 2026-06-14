"""Shared utilities for season scripts."""

import os
from datetime import date, datetime, timedelta, timezone

import yaml


def _load_lb(path: str) -> dict:
    if os.path.exists(path):
        with open(path) as f:
            return yaml.safe_load(f) or {}
    return {}


def _save_lb(data: dict, path: str) -> None:
    data["last_updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)


def _today() -> date:
    raw = os.environ.get("TODAY")
    if not raw:
        return date.today()
    try:
        return date.fromisoformat(raw)
    except ValueError:
        raise ValueError(f"TODAY env var must be YYYY-MM-DD, got: {raw!r}") from None


def current_quarter(today: date | None = None) -> str:
    """Return e.g. '2026-Q3' for the quarter containing today."""
    d = today or _today()
    q = (d.month - 1) // 3 + 1
    return f"{d.year}-Q{q}"


def is_tournament_monday(today: date | None = None) -> bool:
    """Return True if today is the first Monday of a new quarter."""
    d = today or _today()
    if d.weekday() != 0:  # 0 = Monday
        return False
    return d.month in (1, 4, 7, 10) and d.day <= 7


def next_tournament_monday(today: date | None = None) -> date:
    """Return the next date that is a tournament Monday (on or after today)."""
    d = today or _today()
    for i in range(100):
        candidate = d + timedelta(days=i)
        if is_tournament_monday(candidate):
            return candidate
    raise ValueError("No tournament Monday found in next 100 days")
