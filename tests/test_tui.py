def test_tuiadapter_init():
    from game.tui import TuiAdapter

    adapter = TuiAdapter(n_games=100)
    assert adapter._n_games == 100
    assert adapter._app is None


def test_resolve_player_names_passthrough_unknown():
    """Names not matching any class name are returned unchanged."""
    import os

    from game.tui import resolve_player_names

    lb_path = os.environ.get("LEADERBOARD_PATH", "leaderboard.yaml")
    result = resolve_player_names(["Nonexistent"], lb_path, "players")
    assert result == ["Nonexistent"]


def test_resolve_player_names_display_name_passthrough():
    """Display names that don't match a class name are returned unchanged."""
    import os

    from game.tui import resolve_player_names

    lb_path = os.environ.get("LEADERBOARD_PATH", "leaderboard.yaml")
    result = resolve_player_names(["The Oracle"], lb_path, "players")
    # "The Oracle" is a display name, not a class name — returned as-is.
    # (Using the class name "Oracle" here would test the resolution path
    # instead, since players/oracle.py's class Oracle has that display name.)
    assert "The Oracle" in result
