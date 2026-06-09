#!/usr/bin/env python3
"""Validate a modified player file and update display_name in leaderboard.yaml.

Usage: lb_update_name.py <player_file>
Exits 0 on success (prints updated line or no-change line).
Exits 1 on validation failure (prints ERROR line).
"""

import importlib.util
import sys
from pathlib import Path

import yaml

player_file = sys.argv[1]
p = Path(player_file)

spec = importlib.util.spec_from_file_location(p.stem, p)
if spec is None or spec.loader is None:
    print(f"ERROR: Cannot load {player_file}")
    sys.exit(1)
m = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(m)
except Exception as e:
    print(f"ERROR: Failed to import {player_file}: {e}")
    sys.exit(1)

cls = next(
    (
        getattr(m, n)
        for n in dir(m)
        if n.lower() == p.stem.lower() and isinstance(getattr(m, n), type)
    ),
    None,
)
if cls is None:
    print(f"ERROR: No class matching {p.stem} found")
    sys.exit(1)

class_name = cls.__name__
display_name = getattr(cls, "name", class_name)

if len(display_name) > 20:
    print(f"ERROR: name '{display_name}' exceeds 20 characters")
    sys.exit(1)
if "(" in display_name or ")" in display_name:
    print("ERROR: name may not contain parentheses")
    sys.exit(1)

with open("leaderboard.yaml") as f:
    data = yaml.safe_load(f) or {}

if class_name in data.get("players", {}):
    data["players"][class_name]["display_name"] = display_name
    with open("leaderboard.yaml", "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)
    print(f"Updated display_name for {class_name} to '{display_name}'")
else:
    print(f"WARNING: {class_name} not found in leaderboard; no update made")
