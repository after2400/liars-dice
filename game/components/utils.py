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


def roll_dice(hands: list):
    for h in hands:
        h["hand"] = r.choices(FACES, k=h["n_dice"])
    return hands
