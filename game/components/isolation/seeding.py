import hashlib


def derive_worker_seed(game_seed: int, player_name: str) -> bytes:
    return hashlib.sha256(
        b"liars-dice/worker-rng:" + str(game_seed).encode() + b"|" + player_name.encode()
    ).digest()
