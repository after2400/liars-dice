import importlib.util
import os
import random as r
from dataclasses import dataclass

from game.components.security import enforce, secure_environment

FACES = list(range(1, 7))


@dataclass
class PlayerSpec:
    """A loaded player plus the source info needed to reload it elsewhere.

    Isolated workers (game/components/isolation/worker.py) reload a player
    BY ABSOLUTE FILE PATH in a fresh interpreter, not by module name —
    `spec_from_file_location`'s module name is a bare stem, not importable
    after a `multiprocessing.get_context("spawn")` re-exec. `abs_file_path`
    exists so `run_series`'s isolated path (game/components/series.py) can
    build a `WorkerConfig` for each player without re-deriving that path.
    """

    player_obj: object
    abs_file_path: str
    class_name: str


def import_player_specs_from_dir(directory) -> list["PlayerSpec"]:
    # Importing and instantiating a player runs its untrusted module-level and
    # __init__ code — the once-per-run window where a hostile bot would place
    # file/network exfil. Install the audit hook (idempotent) and mark the whole
    # load as player-controlled so forbidden syscalls are blocked here too, not
    # only inside algo().
    secure_environment()
    specs: list[PlayerSpec] = []
    for filename in os.listdir(directory):
        if filename.endswith(".py"):
            module_name = filename[:-3]
            module_path = os.path.join(directory, filename)
            abs_file_path = os.path.abspath(module_path)
            spec = importlib.util.spec_from_file_location(module_name, module_path)
            module = importlib.util.module_from_spec(spec)
            with enforce():
                spec.loader.exec_module(module)
            player_class = next(
                (
                    getattr(module, name)
                    for name in dir(module)
                    if name.lower() == module_name.lower()
                    and isinstance(getattr(module, name), type)
                ),
                None,
            )
            if player_class is not None:
                with enforce():
                    player_obj = player_class()
                player_spec = PlayerSpec(
                    player_obj=player_obj,
                    abs_file_path=abs_file_path,
                    class_name=player_class.__name__,
                )
                # Tag the instance with its own spec so callers that only ever go
                # through import_player_classes_from_dir (every current call site —
                # season.py/tournament.py/quarter.py/__main__.py — none of which are
                # changed in this task) still let it travel invisibly to wherever a
                # player object ends up, e.g. run_series's isolated path, which needs
                # the source file + class name to build a WorkerConfig. Private
                # attribute, not part of the player interface.
                player_obj._isolation_spec = player_spec
                specs.append(player_spec)
    return specs


def import_player_classes_from_dir(directory):
    """Thin wrapper over import_player_specs_from_dir for callers that only need
    the instantiated player objects. See PlayerSpec / import_player_specs_from_dir
    for the full load (also tags each returned object with `._isolation_spec`)."""
    return [s.player_obj for s in import_player_specs_from_dir(directory)]


def apply_display_names(players: list, lb_players: dict) -> None:
    """Set player.name to the deduplicated display name from the leaderboard.

    When two players share the same display_name, build_display_names appends
    a (github_username) suffix so each in-game name is unique. Players not
    registered in lb_players are left untouched.
    """
    from game.components.leaderboard import build_display_names

    display_names = build_display_names(lb_players)
    for p in players:
        class_name = type(p).__name__
        if class_name in display_names:
            p.name = display_names[class_name]


def roll_dice(hands: list):
    for h in hands:
        h["hand"] = r.choices(FACES, k=h["n_dice"])
    return hands
