#!/usr/bin/env python3
"""Print "true" if a player whose class name matches the given file stem
(case-insensitive) is already in leaderboard.yaml, else "false".

The leaderboard is keyed by class name, and the player contract guarantees the
class name equals the filename stem (case-insensitive), so this is a pure-data
uniqueness check that never imports the player file.

Usage: lb_has_player.py <stem>
Always exits 0.
"""

import sys

import yaml

stem = sys.argv[1]
try:
    with open("leaderboard.yaml") as f:
        data = yaml.safe_load(f) or {}
    for key in data.get("players", {}):
        if key.lower() == stem.lower():
            print("true")
            sys.exit(0)
except Exception:
    pass
print("false")
