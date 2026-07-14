from game.components.bets import Bet
from game.components.isolation.readmodel import ReadModelReader, ReadModelWriter
from game.components.stats import GameStats

_ALL_STATS_PROPERTIES = [
    "bluff_rate",
    "bluff_rate_by_face",
    "raw_bluff_rate",
    "raw_bluff_rate_by_face",
    "challenge_rate",
    "challenge_success_rate",
    "face_bias",
    "bid_increment",
    "opening_aggression",
    "mean_held_quantity_by_face",
    "revealed_hand_frequency",
    "rounds_with_hand",
    "current_round_velocity",
    "ones_are_wild",
    "dice_counts",
    "die_losses_from_bluff",
    "die_losses_from_challenge",
    "challenge_success_by_face",
    "challenge_count_by_face",
    "rounds_played",
    "games_played",
    "penalty_count",
]


def _populate(s: GameStats):
    s.start_game(["Alice", "Bob"])
    s.update_bet(
        {
            "game": 1,
            "round": 1,
            "player": "Alice",
            "bet": __import__("game.components.bets", fromlist=["Bet"]).Bet(2, 5, "Alice"),
            "dice_count": 5,
        },
        is_opening_bid=True,
        total_dice=10,
    )


def test_stats_property_values_identical_across_boundary():
    src = GameStats()
    _populate(src)
    w = ReadModelWriter(size_bytes=1 << 20)
    try:
        w.publish_stats(src)
        got = ReadModelReader(w.name).stats_view()
        assert got.opening_aggression == src.opening_aggression
        assert got.face_bias == src.face_bias
        assert got.dice_counts == src.dice_counts
    finally:
        w.close()
        w.unlink()


def test_stats_view_returns_empty_gamestats_before_first_publish():
    """A worker may open its ReadModelReader before the parent's first
    publish_stats() call for the game. stats_view() must not crash — it
    should behave like GameContext's own `stats=None -> GameStats()` default."""
    w = ReadModelWriter(size_bytes=1 << 20)
    try:
        got = ReadModelReader(w.name).stats_view()
        assert got.opening_aggression == {}
        assert got.dice_counts == {}
        assert got.current_round_velocity == 1.0
        assert got.ones_are_wild is True
    finally:
        w.close()
        w.unlink()


def test_all_stats_properties_survive_the_boundary():
    """Broader than the brief's spot-check: every @property on GameStats,
    after a realistic sequence of start_game/update_bet/update_outcome/
    reset_round/record_penalty calls, must match exactly across the boundary."""
    src = GameStats()
    src.start_game(["Alice", "Bob", "Carol"])
    src.update_bet(
        {"game": 1, "round": 1, "player": "Alice", "bet": Bet(2, 5, "Alice"), "dice_count": 5},
        is_opening_bid=True,
        total_dice=15,
    )
    src.update_bet(
        {"game": 1, "round": 1, "player": "Bob", "bet": Bet(3, 5, "Bob"), "dice_count": 5},
        is_opening_bid=False,
        total_dice=15,
    )
    src.update_outcome(
        {
            "bidder": "Bob",
            "challenger": "Alice",
            "bet_held": False,
            "final_bet": Bet(3, 5, "Bob"),
            "hands": {"Alice": (1, 2, 3, 4, 5), "Bob": (1, 1, 2, 3, 4), "Carol": (6, 6, 6)},
            "loser": "Bob",
        }
    )
    src.reset_round(2)
    src.record_penalty("Carol")

    w = ReadModelWriter(size_bytes=1 << 20)
    try:
        w.publish_stats(src)
        got = ReadModelReader(w.name).stats_view()
        for prop in _ALL_STATS_PROPERTIES:
            assert getattr(got, prop) == getattr(src, prop), f"mismatch on {prop!r}"
    finally:
        w.close()
        w.unlink()


def test_publish_stats_double_buffers_so_second_publish_lands_on_the_other_buffer():
    """Verifies real double-buffering, not just a single unprotected write: two
    publishes in a row must alternate which physical buffer holds the data
    (the header's stats_active flips 0 -> 1 -> 0 -> ...), and each publish's
    snapshot must be fully readable afterward."""
    src = GameStats()
    src.start_game(["Alice", "Bob"])

    w = ReadModelWriter(size_bytes=1 << 20)
    try:
        w.publish_stats(src)
        active_after_first, _len0, _len1 = w._read_stats_header()

        src.update_bet(
            {"game": 1, "round": 1, "player": "Alice", "bet": Bet(2, 5, "Alice"), "dice_count": 5},
            is_opening_bid=True,
            total_dice=10,
        )
        w.publish_stats(src)
        active_after_second, _len0b, _len1b = w._read_stats_header()

        assert active_after_second != active_after_first

        got = ReadModelReader(w.name).stats_view()
        assert got.opening_aggression == src.opening_aggression
        assert got.dice_counts == src.dice_counts
    finally:
        w.close()
        w.unlink()
