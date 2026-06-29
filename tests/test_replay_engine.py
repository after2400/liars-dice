import pytest

from game.components.bets import Bet


class _Bidder:
    """Minimal player: bids 1×1 on first turn, calls liar thereafter."""

    def __init__(self, name: str) -> None:
        self.name = name

    def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):
        if prior_bet is None:
            return Bet(1, 1, self.name)
        return None


class _BidderA(_Bidder):
    """Distinct subclass so type().__name__ differs from _BidderB."""

    pass


class _BidderB(_Bidder):
    """Distinct subclass so type().__name__ differs from _BidderA."""

    pass


def _two_players():
    return [_BidderA("A"), _BidderB("B")]


def test_game_orchestrator_with_seed_is_deterministic():
    from game.components.script import game_orchestrator

    players = _two_players()
    winner1 = game_orchestrator(players, seed=12345)
    winner2 = game_orchestrator(players, seed=12345)
    assert winner1.name == winner2.name


def test_game_orchestrator_different_seeds_differ():
    """Different seeds should occasionally produce different winners (probabilistic)."""
    from game.components.script import game_orchestrator

    players = _two_players()
    results = {game_orchestrator(players, seed=s).name for s in range(50)}
    assert len(results) == 2  # both players win at least once across 50 seeds


def test_run_series_record_seeds_captures_one_per_game():
    from game.components.series import run_series

    seeds: list[int] = []
    run_series(_two_players(), n_games=5, record_seeds=seeds)
    assert len(seeds) == 5
    assert all(isinstance(s, int) for s in seeds)


def test_run_series_replay_seeds_deterministic():
    from game.components.series import run_series

    seeds: list[int] = []

    # Record seeds and wins from first run
    result_a = run_series(_two_players(), n_games=10, record_seeds=seeds)

    # Replay seeds with fresh player instances
    result_b = run_series(_two_players(), n_games=10, replay_seeds=seeds)

    # Same seeds with identical player classes should produce identical wins
    assert result_a.wins == result_b.wins
    assert sum(result_a.wins.values()) == 10
    # Verify we have distinct keys for each player (not collapsed to single key)
    assert len(result_a.wins) == 2
    assert "_BidderA" in result_a.wins
    assert "_BidderB" in result_a.wins


def test_run_series_mutual_exclusion_raises():
    from game.components.series import run_series

    with pytest.raises(ValueError, match="mutually exclusive"):
        run_series(_two_players(), n_games=2, record_seeds=[], replay_seeds=[1, 2])


def test_run_series_replay_seeds_length_mismatch_raises():
    from game.components.series import run_series

    with pytest.raises(ValueError, match="length"):
        run_series(_two_players(), n_games=3, replay_seeds=[1, 2])


def test_run_series_no_seed_args_unchanged():
    """Baseline: no seed args still runs without error."""
    from game.components.series import run_series

    result = run_series(_two_players(), n_games=3)
    assert sum(result.wins.values()) == 3


def test_run_series_replay_deterministic_with_global_random_player():
    """Players calling global random.random() must produce identical results on replay.

    Regression test: before seeding the global random module per-game, players
    like Cleo/Rick/Nuke that call random.random() directly produced different
    outcomes between recording and replay runs.
    """
    import random as _random

    from game.components.bets import Bet
    from game.components.series import run_series

    class _GlobalRandomPlayer:
        def __init__(self, name: str) -> None:
            self.name = name

        def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):
            if prior_bet is None:
                return Bet(1, 1, self.name)
            return None if _random.random() < 0.4 else Bet(prior_bet.quantity + 1, 1, self.name)

    class _GRA(_GlobalRandomPlayer):
        pass

    class _GRB(_GlobalRandomPlayer):
        pass

    def _players():
        return [_GRA("A"), _GRB("B")]

    seeds: list[int] = []
    result_a = run_series(_players(), n_games=30, record_seeds=seeds)
    result_b = run_series(_players(), n_games=30, replay_seeds=seeds)

    assert result_a.wins == result_b.wins
