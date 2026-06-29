def _make_stats(player: str, games: int = 100, wins: int = 40):
    """Create a minimal GameStats-like object for testing."""
    from game.components.stats import GameStats

    s = GameStats()
    # Manually set internal state for the fields render functions read
    s._games_played[player] = games
    s._rounds_played[player] = games * 10
    s._penalty_count[player] = 2
    s._die_losses_from_bluff[player]["EvilStewie"] = 15
    s._die_losses_from_challenge[player]["EvilStewie"] = 12
    s._challenge_success_by_face[player][1] = 7
    s._challenge_count_by_face[player][1] = 10
    return s


def test_bar_empty_when_total_zero():
    from game.tui.widgets import _bar

    result = _bar(0, 0)
    assert "░" in result
    assert "█" not in result


def test_bar_full_when_value_equals_total():
    from game.tui.widgets import _bar

    result = _bar(10, 10, width=5)
    assert result == "█████"


def test_bar_half():
    from game.tui.widgets import _bar

    result = _bar(5, 10, width=10)
    assert result.count("█") == 5
    assert result.count("░") == 5


def test_pct_zero_denominator():
    from game.tui.widgets import _pct

    assert _pct(0, 0) == "—"


def test_pct_half():
    from game.tui.widgets import _pct

    assert _pct(1, 2) == "50.0%"


def _render_to_str(renderable) -> str:
    import io

    from rich.console import Console

    buf = io.StringIO()
    Console(file=buf, width=120, highlight=False).print(renderable)
    return buf.getvalue()


def test_render_left_contains_expected_content():
    from game.tui.widgets import _render_left

    stats = _make_stats("Oracle")
    step_tiers = {"CH": ({"Oracle": 20, "EvilStewie": 30}, stats, 100)}
    result = _render_left("Oracle", 100, step_tiers, {"Oracle": 20, "EvilStewie": 30}, stats, 50)
    text = _render_to_str(result)
    assert "Win Rate" in text
    assert "Die Losses" in text
    assert "Challenge Accuracy" in text


def test_render_right_contains_expected_content():
    from game.tui.widgets import PlayerAggregate, TierStats, _render_right

    agg = PlayerAggregate(
        total_games=100,
        wins=40,
        per_tier={"CH": TierStats(games=100, wins=40, rounds_played=1000)},
    )
    result = _render_right("Oracle", agg)
    text = _render_to_str(result)
    assert "Win Rate" in text
    assert "40.0%" in text


def test_player_aggregate_defaults():
    from game.tui.widgets import PlayerAggregate

    agg = PlayerAggregate()
    assert agg.total_games == 0
    assert agg.wins == 0
    assert agg.die_losses_from_bluff == {}
    assert agg.challenge_success_by_face == {}
