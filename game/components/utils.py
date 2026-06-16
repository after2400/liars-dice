import importlib
import os
import random as r

FACES = list(range(1, 7))


def import_player_classes_from_dir(directory):
    player_objects = []
    for filename in os.listdir(directory):
        if filename.endswith(".py"):
            module_name = filename[:-3]
            module_path = os.path.join(directory, filename)
            spec = importlib.util.spec_from_file_location(module_name, module_path)
            module = importlib.util.module_from_spec(spec)
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
                player_objects.append(player_class())
    return player_objects


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
