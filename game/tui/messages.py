"""Typed Textual message classes for TUI ↔ simulation thread communication."""

from __future__ import annotations

from textual.message import Message


class StepStarted(Message):
    """Fired once per Monday step (Tournament / Week N) in a quarter run."""

    def __init__(self, label: str) -> None:
        super().__init__()
        self.label = label


class SeriesStarted(Message):
    def __init__(self, label: str) -> None:
        super().__init__()
        self.label = label


class GameComplete(Message):
    def __init__(self, game_num: int, wins: dict[str, int], stats) -> None:
        super().__init__()
        self.game_num = game_num
        self.wins = wins
        self.stats = stats


class SeriesComplete(Message):
    def __init__(self, label: str, result) -> None:
        super().__init__()
        self.label = label
        self.result = result


class SimulationComplete(Message):
    pass


class LogLine(Message):
    def __init__(self, text: str) -> None:
        super().__init__()
        self.text = text


class DrillInPlayer(Message):
    def __init__(self, player: str) -> None:
        super().__init__()
        self.player = player
