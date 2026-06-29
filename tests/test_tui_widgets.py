"""Tests for StandingsWidget interactive behavior."""


def test_standings_widget_can_focus():
    """StandingsWidget must declare can_focus = True for keyboard nav to work."""
    from game.tui.widgets import StandingsWidget

    assert StandingsWidget.can_focus is True


def test_standings_widget_bindings_include_required_keys():
    """StandingsWidget must have up/down/enter bindings."""
    from game.tui.widgets import StandingsWidget

    binding_keys = {b[0] for b in StandingsWidget.BINDINGS}
    assert "up" in binding_keys, "missing 'up' binding"
    assert "down" in binding_keys, "missing 'down' binding"
    assert "enter" in binding_keys, "missing 'enter' binding"


def test_standings_widget_action_drill_in_posts_message():
    """action_drill_in posts DrillInPlayer for the cursor row."""
    from game.tui.messages import DrillInPlayer
    from game.tui.widgets import StandingsWidget

    widget = StandingsWidget()

    posted = []

    def _fake_post(msg):
        posted.append(msg)

    widget.post_message = _fake_post  # type: ignore[method-assign]

    # Populate with data so cursor points to a real player
    class _FakeStats:
        games_played = {"Oracle": 10}
        rounds_played = {"Oracle": 30}

    widget._players = ["Oracle", "EvilStewie"]
    widget._cursor = 0

    widget.action_drill_in()

    assert len(posted) == 1
    assert isinstance(posted[0], DrillInPlayer)
    assert posted[0].player == "Oracle"


def test_standings_widget_cursor_clamps():
    """cursor_up/down stay within bounds."""
    from game.tui.widgets import StandingsWidget

    widget = StandingsWidget()
    widget._players = ["A", "B", "C"]
    widget._cursor = 0

    # up from 0 stays at 0
    widget.action_cursor_up()
    assert widget._cursor == 0

    # down moves correctly
    widget.action_cursor_down()
    assert widget._cursor == 1
    widget.action_cursor_down()
    assert widget._cursor == 2

    # down at last row stays
    widget.action_cursor_down()
    assert widget._cursor == 2


def test_standings_widget_drill_in_no_players_is_noop():
    """action_drill_in with empty player list does not post a message."""
    from game.tui.widgets import StandingsWidget

    widget = StandingsWidget()
    posted = []
    widget.post_message = lambda msg: posted.append(msg)  # type: ignore[method-assign]

    widget.action_drill_in()

    assert posted == []
