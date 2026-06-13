import argparse
import json
import logging
import os
from pathlib import Path

import yaml

project_root = Path(__file__).parent.parent


def _parse_args():
    p = argparse.ArgumentParser()
    p.add_argument(
        "--tier",
        choices=["PRM", "CH", "L1", "inactive"],
        default=None,
        help="Run only players in this tier",
    )
    p.add_argument("--results-file", default=None, help="Write wins dict as JSON to this path")
    p.add_argument(
        "--no-game-results",
        action="store_true",
        help="Suppress per-game result lines; show only the final summary table",
    )
    p.add_argument(
        "--players",
        nargs="+",
        default=None,
        help="Run exactly these player class names (overrides --tier)",
    )
    p.add_argument("n_games", type=int, nargs="?", default=1)
    p.add_argument("top_n", type=int, nargs="?", default=4)
    return p.parse_args()


args = _parse_args()

# --- Logging setup ---

file_handler = logging.FileHandler("gamelog.log", mode="w")
file_handler.setLevel(logging.DEBUG)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

file_fmt = logging.Formatter("%(name)s - %(levelname)s - %(message)s")
file_handler.setFormatter(file_fmt)


class _GameFormatter(logging.Formatter):
    def format(self, record):
        msg = record.getMessage()
        if not msg:
            return ""
        if record.levelno >= logging.WARNING:
            return f"[{record.levelname}] {msg}"
        return msg


class _SeriesConsoleFilter(logging.Filter):
    def filter(self, record):
        return record.name == "game.components.series"


console_handler.setFormatter(_GameFormatter())
console_handler.addFilter(_SeriesConsoleFilter())
logging.basicConfig(level=logging.DEBUG, handlers=[file_handler, console_handler])

# Suppress per-game lines when --no-game-results is set
if args.no_game_results:
    console_handler.setLevel(logging.WARNING)

# --- Imports after logging setup ---

from game.components.series import format_results, run_series  # noqa: E402
from game.components.utils import import_player_classes_from_dir  # noqa: E402

# --- Main ---

N_GAMES = args.n_games
TOP_N = args.top_n

# Allow LEADERBOARD_PATH env var override for testing
_lb_path = Path(os.environ.get("LEADERBOARD_PATH", str(project_root / "leaderboard.yaml")))
_lb_data = yaml.safe_load(open(_lb_path)) if _lb_path.exists() else {}
_lb_players = _lb_data.get("players", {})

all_players = import_player_classes_from_dir(str(project_root / "players"))

if args.players:
    player_names = set(args.players)
    players = [p for p in all_players if type(p).__name__ in player_names]
elif args.tier:
    if args.tier in ("PRM", "CH"):
        # Registered tier players + unregistered challengers (not yet in leaderboard)
        players = [
            p
            for p in all_players
            if _lb_players.get(type(p).__name__, {}).get("tier") == args.tier
            or type(p).__name__ not in _lb_players
        ]
    else:
        # L1 and inactive: registered players in that exact tier only
        players = [
            p for p in all_players if _lb_players.get(type(p).__name__, {}).get("tier") == args.tier
        ]
else:
    # No tier filter: run everyone in the players/ directory
    players = all_players

if len(players) < 2:
    print(f"[skip] Only {len(players)} player(s) in --tier {args.tier} — no game run.")
    raise SystemExit(0)

if not args.no_game_results:
    print(f"Playing: {[type(p).__name__ for p in players]}")

wins = run_series(players, N_GAMES)
print(format_results(wins, N_GAMES))

if args.results_file:
    with open(args.results_file, "w") as f:
        json.dump(wins, f)
