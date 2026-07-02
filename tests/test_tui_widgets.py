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


def test_app_inner_tab_id_syncs_on_outer_tab_change():
    """`_current_step_inner_id` must follow the outer tab that is activated."""
    import threading
    from types import SimpleNamespace

    from game.tui.app import LiarsDiceApp

    app = LiarsDiceApp(n_games=10, ready_event=threading.Event())

    # Simulate two steps having been started
    app._step_count = 2
    app._current_step_inner_id = "step-tabs-2"
    app._outer_tab_ids = ["live", "step-1", "step-2"]

    # Fire a synthetic TabActivated pointing at "step-1"
    event = SimpleNamespace(
        tabbed_content=SimpleNamespace(id="tabs"),
        pane=SimpleNamespace(id="step-1"),
    )
    app.on_tabbed_content_tab_activated(event)

    assert app._current_step_inner_id == "step-tabs-1"

    # Switching to a non-step tab (live) must not change the inner id
    event2 = SimpleNamespace(
        tabbed_content=SimpleNamespace(id="tabs"),
        pane=SimpleNamespace(id="live"),
    )
    app.on_tabbed_content_tab_activated(event2)
    assert app._current_step_inner_id == "step-tabs-1"

    # Events from inner TabbedContents must be ignored
    event3 = SimpleNamespace(
        tabbed_content=SimpleNamespace(id="step-tabs-1"),
        pane=SimpleNamespace(id="hist-1"),
    )
    app.on_tabbed_content_tab_activated(event3)
    assert app._current_step_inner_id == "step-tabs-1"


def test_standings_cursor_highlight_excludes_bar():
    """The 'bold reverse' cursor highlight must not cover the bar chart column."""
    from game.tui.widgets import _BAR_FULL, StandingsWidget

    widget = StandingsWidget()

    class _FakeStats:
        games_played = {"Oracle": 100, "EvilStewie": 100}

    widget._players = ["Oracle", "EvilStewie"]
    widget._wins = {"Oracle": 50, "EvilStewie": 30}
    widget._stats = _FakeStats()
    widget._cursor = 0  # Oracle selected
    widget._game_num = 50
    widget._n_games = 100

    result = widget.render()
    plain = result.plain

    bar_pos = plain.index(_BAR_FULL)
    for span in result._spans:
        if span.start <= bar_pos < span.end:
            assert "reverse" not in str(span.style), (
                f"bar character at pos {bar_pos} must not be reverse-highlighted (span: {span})"
            )


def test_standings_widget_name_column_widens_for_longest_name():
    """A long player name must not push later rows' columns out of alignment."""
    from game.tui.widgets import StandingsWidget

    widget = StandingsWidget()

    class _FakeStats:
        games_played = {"Ripley": 500, "Liar², Pants on Fire": 500, "Cleo": 500}

    widget._players = ["Ripley", "Liar², Pants on Fire", "Cleo"]
    widget._wins = {"Ripley": 221, "Liar², Pants on Fire": 2, "Cleo": 0}
    widget._stats = _FakeStats()
    widget._game_num = 500
    widget._n_games = 500

    lines = [line for line in widget.render().plain.splitlines() if line.strip()]
    data_lines = lines[1:]  # drop the title line

    assert all(len(line) == len(data_lines[0]) for line in data_lines)
    # every row's win-count column starts at the same offset
    longest_name_len = len("Liar², Pants on Fire")
    win_col_start = 2 + longest_name_len + 2
    for line, wins in zip(data_lines, [221, 2, 0]):
        assert line[win_col_start : win_col_start + 5].strip() == str(wins)


def test_standings_widget_drill_in_no_players_is_noop():
    """action_drill_in with empty player list does not post a message."""
    from game.tui.widgets import StandingsWidget

    widget = StandingsWidget()
    posted = []
    widget.post_message = lambda msg: posted.append(msg)  # type: ignore[method-assign]

    widget.action_drill_in()

    assert posted == []


# ── ThisWeekPanel ──────────────────────────────────────────────────────────────


def test_this_week_panel_can_focus():
    from game.tui.widgets import ThisWeekPanel

    assert ThisWeekPanel.can_focus is True


def test_this_week_panel_has_copy_and_escape_bindings():
    from game.tui.widgets import ThisWeekPanel

    keys = {b[0] for b in ThisWeekPanel.BINDINGS}
    assert "c" in keys, "missing 'c' (copy) binding"
    assert "escape" in keys, "missing 'escape' (close) binding"


def test_this_week_panel_copy_calls_app_clipboard():
    from unittest.mock import MagicMock, PropertyMock, patch

    from game.tui.widgets import ThisWeekPanel

    panel = ThisWeekPanel(player="Oracle", n_games=100)
    mock_app = MagicMock()
    with patch.object(type(panel), "app", new_callable=PropertyMock, return_value=mock_app):
        panel.action_copy_to_clipboard()

    mock_app.copy_to_clipboard.assert_called_once()
    text = mock_app.copy_to_clipboard.call_args[0][0]
    assert "Oracle" in text
    assert len(text) > 10


# ── SimTotalPanel ──────────────────────────────────────────────────────────────


def test_sim_total_panel_can_focus():
    from game.tui.widgets import SimTotalPanel

    assert SimTotalPanel.can_focus is True


def test_sim_total_panel_has_copy_and_escape_bindings():
    from game.tui.widgets import SimTotalPanel

    keys = {b[0] for b in SimTotalPanel.BINDINGS}
    assert "c" in keys, "missing 'c' (copy) binding"
    assert "escape" in keys, "missing 'escape' (close) binding"


def test_sim_total_panel_copy_calls_app_clipboard():
    from unittest.mock import MagicMock, PropertyMock, patch

    from game.tui.widgets import PlayerAggregate, SimTotalPanel, TierStats

    panel = SimTotalPanel(player="Oracle")
    agg = PlayerAggregate(
        total_games=500,
        wins=120,
        per_tier={"PRM": TierStats(games=500, wins=120, rounds_played=5000)},
    )
    panel.update_aggregate(agg)
    mock_app = MagicMock()
    with patch.object(type(panel), "app", new_callable=PropertyMock, return_value=mock_app):
        panel.action_copy_to_clipboard()

    mock_app.copy_to_clipboard.assert_called_once()
    text = mock_app.copy_to_clipboard.call_args[0][0]
    assert "Oracle" in text
    assert "500" in text


# ── LogPanel ───────────────────────────────────────────────────────────────────


def test_log_panel_can_focus():
    from game.tui.widgets import LogPanel

    assert LogPanel.can_focus is True


def test_log_panel_has_copy_binding():
    from game.tui.widgets import LogPanel

    keys = {b[0] for b in LogPanel.BINDINGS}
    assert "c" in keys, "missing 'c' (copy) binding"


def test_log_panel_copy_calls_app_clipboard():
    from unittest.mock import MagicMock, PropertyMock, patch

    from game.tui.widgets import LogPanel

    panel = LogPanel()
    panel.write_line("[bold]── Week 1 ──[/bold]")
    panel.write_line("game 50: Oracle leads (30 wins)")
    mock_app = MagicMock()
    with patch.object(type(panel), "app", new_callable=PropertyMock, return_value=mock_app):
        panel.action_copy_to_clipboard()

    mock_app.copy_to_clipboard.assert_called_once()
    text = mock_app.copy_to_clipboard.call_args[0][0]
    assert "Week 1" in text
    assert "Oracle leads" in text
    assert "[bold]" not in text  # markup stripped for the clipboard


def test_log_panel_copy_does_not_wrap_wide_lines():
    """Lines wider than the 120-column default (e.g. the perf table with
    memory columns) must round-trip on one line, not get hard-wrapped."""
    from unittest.mock import MagicMock, PropertyMock, patch

    from game.tui.widgets import LogPanel

    panel = LogPanel()
    wide_line = "  ".join(f"col{i}" for i in range(30))  # comfortably over 120 chars
    assert len(wide_line) > 120
    panel.write_line(wide_line)
    mock_app = MagicMock()
    with patch.object(type(panel), "app", new_callable=PropertyMock, return_value=mock_app):
        panel.action_copy_to_clipboard()

    text = mock_app.copy_to_clipboard.call_args[0][0]
    assert wide_line in text  # unbroken — not split across a hard-wrapped line


# ── PlayerStatsPanel container ─────────────────────────────────────────────────


def test_player_stats_panel_update_aggregate_before_mount_does_not_raise():
    """update_aggregate called before mounting must not raise MountError."""
    from game.tui.widgets import PlayerAggregate, PlayerStatsPanel

    panel = PlayerStatsPanel(player="Oracle", n_games=100)
    agg = PlayerAggregate(total_games=10, wins=3)

    # Must not raise — widget is not yet attached to a DOM
    panel.update_aggregate(agg)


def test_player_stats_panel_update_step_data_before_mount_does_not_raise():
    """update_step_data called before mounting must not raise."""
    from game.tui.widgets import PlayerStatsPanel

    class _FakeStats:
        games_played = {"Oracle": 10}
        rounds_played = {"Oracle": 100}
        penalty_count = {"Oracle": 0}
        die_losses_from_bluff = {}
        die_losses_from_challenge = {}
        challenge_success_by_face = {}
        challenge_count_by_face = {}

    panel = PlayerStatsPanel(player="Oracle", n_games=100)
    panel.update_step_data({}, {}, _FakeStats(), 5)


def test_player_stats_panel_has_player_attribute():
    from game.tui.widgets import PlayerStatsPanel

    panel = PlayerStatsPanel(player="Oracle", n_games=100)
    assert panel.player == "Oracle"


def test_player_stats_panel_is_not_focusable():
    """The container itself should not be focusable — only its children are."""
    from game.tui.widgets import PlayerStatsPanel

    assert not getattr(PlayerStatsPanel, "can_focus", False)


# ── _to_plain_text helper ──────────────────────────────────────────────────────


def test_to_plain_text_renders_structured_table():
    from rich.panel import Panel
    from rich.table import Table

    from game.tui.widgets import _to_plain_text

    table = Table()
    table.add_column("Name")
    table.add_column("Score")
    table.add_row("Oracle", "42")
    renderable = Panel(table, title="Results")

    text = _to_plain_text(renderable)

    assert "Oracle" in text
    assert "42" in text
    assert "Results" in text
    assert "\033" not in text, "plain text must contain no ANSI escape codes"
