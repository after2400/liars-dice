#!/usr/bin/env python3
"""Print the github_username for the player matching the given file stem.

Usage: lb_owner.py <stem>
Prints the github_username to stdout, or empty string if not found or on error.
Always exits 0.
"""

import sys

import yaml

stem = sys.argv[1]
try:
    with open("leaderboard.yaml") as f:
        data = yaml.safe_load(f) or {}
    for key, val in data.get("players", {}).items():
        if key.lower() == stem.lower():
            print(val.get("github_username", ""))
            sys.exit(0)
except Exception:
    pass
print("")
