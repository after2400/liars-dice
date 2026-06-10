from unittest.mock import MagicMock

import pytest


def _bet(player: str, face: int, quantity: int, game: int = 1, rnd: int = 1) -> dict:
    b = MagicMock()
    b.face = face
    b.quantity = quantity
    return {"game": game, "round": rnd, "player": player, "bet": b}


def _outcome(
    bidder: str,
    challenger: str,
    face: int,
    quantity: int,
    bet_held: bool,
    hands: dict | None = None,
) -> dict:
    fb = MagicMock()
    fb.face = face
    fb.quantity = quantity
    return {
        "game": 1,
        "round": 1,
        "hands": hands or {},
        "final_bet": fb,
        "bidder": bidder,
        "challenger": challenger,
        "bet_held": bet_held,
        "loser": challenger if bet_held else bidder,
    }


# --- bluff_rate ---


def test_bluff_rate_default_before_any_outcome():
    from game.components.stats import GameStats

    stats = GameStats()
    assert "Alice" not in stats.bluff_rate


def test_bluff_rate_after_one_bluff():
    from game.components.stats import GameStats

    stats = GameStats()
    stats.update_outcome(_outcome("Alice", "Bruno", 3, 5, bet_held=False))
    # (1 bluff + 1) / (1 + 0 + 2) = 2/3
    assert stats.bluff_rate["Alice"] == pytest.approx(2 / 3)


def test_bluff_rate_after_one_hold():
    from game.components.stats import GameStats

    stats = GameStats()
    stats.update_outcome(_outcome("Alice", "Bruno", 3, 5, bet_held=True))
    # (0 + 1) / (0 + 1 + 2) = 1/3
    assert stats.bluff_rate["Alice"] == pytest.approx(1 / 3)


# --- bluff_rate_by_face ---


def test_bluff_rate_by_face_after_bluff_on_face():
    from game.components.stats import GameStats

    stats = GameStats()
    stats.update_outcome(_outcome("Alice", "Bruno", 3, 5, bet_held=False))
    # face 3: (1+1)/(1+0+2) = 2/3
    assert stats.bluff_rate_by_face["Alice"][3] == pytest.approx(2 / 3)
    # face 2 (no data): (0+1)/(0+0+2) = 0.5
    assert stats.bluff_rate_by_face["Alice"][2] == pytest.approx(0.5)


# --- current_round_velocity ---


def test_velocity_is_neutral_with_one_bet():
    from game.components.stats import GameStats

    stats = GameStats()
    stats.update_bet(_bet("Alice", 3, 5), is_opening_bid=True, total_dice=20)
    assert stats.current_round_velocity == pytest.approx(1.0)


def test_velocity_computed_from_two_bets():
    from game.components.stats import GameStats

    stats = GameStats()
    stats.update_bet(_bet("Alice", 3, 4), is_opening_bid=True, total_dice=20)
    stats.update_bet(_bet("Bruno", 3, 7), is_opening_bid=False, total_dice=20)
    # velocity = (7 - 4) / 1 = 3.0
    assert stats.current_round_velocity == pytest.approx(3.0)


def test_reset_round_restores_neutral_velocity():
    from game.components.stats import GameStats

    stats = GameStats()
    stats.update_bet(_bet("Alice", 3, 4), is_opening_bid=True, total_dice=20)
    stats.update_bet(_bet("Bruno", 3, 9), is_opening_bid=False, total_dice=20)
    stats.reset_round(2)
    assert stats.current_round_velocity == pytest.approx(1.0)


# --- mean_held_quantity_by_face ---


def test_mean_held_quantity_single_outcome():
    from game.components.stats import GameStats

    stats = GameStats()
    stats.update_outcome(_outcome("Alice", "Bruno", 3, 6, bet_held=True))
    assert stats.mean_held_quantity_by_face["Alice"][3] == pytest.approx(6.0)


def test_mean_held_quantity_averages_multiple():
    from game.components.stats import GameStats

    stats = GameStats()
    stats.update_outcome(_outcome("Alice", "Bruno", 3, 4, bet_held=True))
    stats.update_outcome(_outcome("Alice", "Bruno", 3, 8, bet_held=True))
    assert stats.mean_held_quantity_by_face["Alice"][3] == pytest.approx(6.0)


def test_bluff_not_counted_in_mean_held_quantity():
    from game.components.stats import GameStats

    stats = GameStats()
    stats.update_outcome(_outcome("Alice", "Bruno", 3, 10, bet_held=False))
    assert stats.mean_held_quantity_by_face.get("Alice", {}).get(3) is None


# --- revealed_hand_frequency and rounds_with_hand ---


def test_revealed_hand_frequency_single_round():
    from game.components.stats import GameStats

    stats = GameStats()
    hands = {"Alice": [2, 2, 3, 5, 6]}
    stats.update_outcome(_outcome("Alice", "Bruno", 3, 3, bet_held=False, hands=hands))
    assert stats.revealed_hand_frequency["Alice"][2] == pytest.approx(2 / 5)
    assert stats.revealed_hand_frequency["Alice"][3] == pytest.approx(1 / 5)
    assert stats.revealed_hand_frequency["Alice"][4] == pytest.approx(0.0)


def test_rounds_with_hand_counts_all_players_in_hands():
    from game.components.stats import GameStats

    stats = GameStats()
    hands = {"Alice": [1, 2, 3], "Bruno": [4, 5]}
    stats.update_outcome(_outcome("Alice", "Bruno", 3, 2, bet_held=False, hands=hands))
    assert stats.rounds_with_hand["Alice"] == 1
    assert stats.rounds_with_hand["Bruno"] == 1


def test_rounds_with_hand_accumulates_across_rounds():
    from game.components.stats import GameStats

    stats = GameStats()
    hands = {"Alice": [2, 3]}
    stats.update_outcome(_outcome("Alice", "Bruno", 2, 2, bet_held=True, hands=hands))
    stats.update_outcome(_outcome("Alice", "Bruno", 2, 2, bet_held=False, hands=hands))
    assert stats.rounds_with_hand["Alice"] == 2


# --- raw_bluff_rate ---


def test_raw_bluff_rate_absent_before_outcomes():
    from game.components.stats import GameStats

    stats = GameStats()
    assert "Alice" not in stats.raw_bluff_rate


def test_raw_bluff_rate_is_unsmoothed():
    from game.components.stats import GameStats

    stats = GameStats()
    # 3 bluffs, 1 hold -> raw = 3/4 = 0.75; Laplace would be 4/6 ≈ 0.667
    for _ in range(3):
        stats.update_outcome(_outcome("Alice", "Bruno", 3, 5, bet_held=False))
    stats.update_outcome(_outcome("Alice", "Bruno", 3, 5, bet_held=True))
    assert stats.raw_bluff_rate["Alice"] == pytest.approx(3 / 4)


def test_raw_bluff_rate_by_face_is_unsmoothed():
    from game.components.stats import GameStats

    stats = GameStats()
    # 2 bluffs on face 3, 1 hold on face 3 -> raw = 2/3; Laplace would be 3/5
    for _ in range(2):
        stats.update_outcome(_outcome("Alice", "Bruno", 3, 5, bet_held=False))
    stats.update_outcome(_outcome("Alice", "Bruno", 3, 5, bet_held=True))
    assert stats.raw_bluff_rate_by_face["Alice"][3] == pytest.approx(2 / 3)


def test_raw_bluff_rate_by_face_no_entry_when_no_data_for_face():
    from game.components.stats import GameStats

    stats = GameStats()
    stats.update_outcome(_outcome("Alice", "Bruno", 3, 5, bet_held=False))
    # face 2 has no data — should have no entry (caller uses .get with 0.5 default)
    assert stats.raw_bluff_rate_by_face.get("Alice", {}).get(2) is None
