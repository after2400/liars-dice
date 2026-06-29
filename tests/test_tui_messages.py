def test_series_started_fields():
    from game.tui.messages import SeriesStarted

    msg = SeriesStarted("Pool 0")
    assert msg.label == "Pool 0"


def test_game_complete_fields():
    from game.components.stats import GameStats
    from game.tui.messages import GameComplete

    stats = GameStats()
    msg = GameComplete(42, {"Oracle": 20, "EvilStewie": 10}, stats)
    assert msg.game_num == 42
    assert msg.wins["Oracle"] == 20
    assert msg.stats is stats


def test_series_complete_fields():
    from game.components.series import SeriesResult
    from game.components.stats import GameStats
    from game.tui.messages import SeriesComplete

    result = SeriesResult(wins={"Oracle": 500}, stats=GameStats())
    msg = SeriesComplete("CH Tier", result)
    assert msg.label == "CH Tier"
    assert msg.result is result


def test_simulation_complete_no_fields():
    from game.tui.messages import SimulationComplete

    msg = SimulationComplete()
    assert msg is not None


def test_log_line_fields():
    from game.tui.messages import LogLine

    msg = LogLine("[run] Pool 0: starting")
    assert msg.text == "[run] Pool 0: starting"


def test_drill_in_player_fields():
    from game.tui.messages import DrillInPlayer

    msg = DrillInPlayer("Oracle")
    assert msg.player == "Oracle"
