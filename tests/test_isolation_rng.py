from game.components.isolation.seeding import derive_worker_seed


def test_seed_is_deterministic_and_player_distinct():
    a1 = derive_worker_seed(12345, "Alice")
    a2 = derive_worker_seed(12345, "Alice")
    b = derive_worker_seed(12345, "Bob")
    assert a1 == a2  # deterministic (replayable)
    assert a1 != b  # independent per player
