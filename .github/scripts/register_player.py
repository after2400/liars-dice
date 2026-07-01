#!/usr/bin/env python3
"""Validate a player file and register it in leaderboard.yaml.

Environment variables:
  PLAYER_FILE       path to the player .py file (e.g. players/fred.py)
  GITHUB_USERNAME   the PR author's GitHub login (github.actor)

Exits 0 on success, 1 on validation failure.
Prints "entry_tier=<tier>" to stdout for the workflow to capture.
"""

import importlib.util
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

LEADERBOARD_PATH = os.environ.get("LEADERBOARD_PATH", "leaderboard.yaml")


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_lb():
    if os.path.exists(LEADERBOARD_PATH):
        with open(LEADERBOARD_PATH) as f:
            return yaml.safe_load(f) or {}
    return {"players": {}, "total_runs": 0, "last_updated": _now()}


def _save_lb(data):
    data["last_updated"] = _now()
    with open(LEADERBOARD_PATH, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)


def _detect_entry_tier(lb: dict) -> str:
    from game.components.leaderboard import detect_entry_tier

    return detect_entry_tier(lb)


def main():
    player_file = os.environ["PLAYER_FILE"]
    github_username = os.environ["GITHUB_USERNAME"]
    module_name = Path(player_file).stem  # e.g. "fred" from "players/fred.py"

    # Ensure the repo root (cwd) is on sys.path so player files (and the
    # game.validate import below) can resolve 'game'.
    if "" not in sys.path and "." not in sys.path:
        sys.path.insert(0, "")

    from game.validate import validate_avatar, validate_display_name

    spec = importlib.util.spec_from_file_location(module_name, player_file)
    if spec is None or spec.loader is None:
        print(f"ERROR: Cannot load {player_file} as a Python module.")
        sys.exit(1)
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as e:
        print(f"ERROR: Failed to import {player_file}: {e}")
        sys.exit(1)

    # Find class matching filename (case-insensitive)
    player_class = next(
        (
            getattr(module, name)
            for name in dir(module)
            if name.lower() == module_name.lower() and isinstance(getattr(module, name), type)
        ),
        None,
    )
    if player_class is None:
        print(
            f"ERROR: No class matching '{module_name}' found in {player_file}. "
            f"Class name must match filename (e.g. class Fred in fred.py)."
        )
        sys.exit(1)

    class_name = player_class.__name__
    display_name = getattr(player_class, "name", class_name)

    # Validate display name (shared rules live in game.validate)
    name_error = validate_display_name(display_name)
    if name_error:
        print(f"ERROR: {name_error}")
        sys.exit(1)

    avatar = getattr(player_class, "avatar", None)
    if avatar is not None:
        avatar_error = validate_avatar(avatar)
        if avatar_error:
            print(f"ERROR: {avatar_error}")
            sys.exit(1)

    lb = _load_lb()
    players = lb.setdefault("players", {})

    if class_name in players:
        print(f"Player {class_name} is already registered.")
        print(f"entry_tier={players[class_name]['tier']}")
        return

    entry_tier = _detect_entry_tier(lb)
    now = _now()
    players[class_name] = {
        "display_name": display_name,
        "github_username": github_username,
        "date_added": now,
        "tier": entry_tier,
        "tier_since": now,
        "times_inactive": 0,
        "tier_stats": {},
    }
    if avatar is not None:
        players[class_name]["avatar"] = avatar

    _save_lb(lb)
    print(f"Registered {class_name} (display: {display_name}) as {github_username} in {entry_tier}")
    print(f"entry_tier={entry_tier}")


if __name__ == "__main__":
    main()
