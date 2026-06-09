#!/usr/bin/env python3
"""Remove players from leaderboard.yaml by file path.

Usage: lb_delete.py <players/foo.py> [players/bar.py ...]
Removes each player whose class name (case-insensitive) matches the file stem.
"""

import sys
from pathlib import Path

import yaml

with open("leaderboard.yaml") as f:
    data = yaml.safe_load(f) or {}
for filepath in sys.argv[1:]:
    stem = Path(filepath).stem
    for key in list(data.get("players", {})):
        if key.lower() == stem.lower():
            del data["players"][key]
            break
with open("leaderboard.yaml", "w") as f:
    yaml.dump(data, f, default_flow_style=False, sort_keys=False)
