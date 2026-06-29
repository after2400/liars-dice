"""Textual TUI for live bot tuning during simulation runs."""

from __future__ import annotations

import sys
import threading
from collections.abc import Callable

from game.tui.app import LiarsDiceApp
from game.tui.messages import (
    GameComplete,
    SeriesComplete,
    SeriesStarted,
    SimulationComplete,
    StepStarted,
)
from game.tui.widgets import LogStream


def resolve_player_names(names: list[str], lb_path: str, players_dir: str) -> list[str]:
    """Map class names to display names so --tui works with either form."""
    from game.components.utils import apply_display_names, import_player_classes_from_dir
    from game.season.utils import _load_lb

    all_players = import_player_classes_from_dir(players_dir)
    apply_display_names(all_players, _load_lb(lb_path).get("players", {}))
    name_map = {type(p).__name__: p.name for p in all_players}
    return [name_map.get(n, n) for n in names]


class TuiAdapter:
    """Public interface for the Textual TUI, replacing the legacy Rich Dashboard.

    display_names: class-name → display-name map. When provided, wins dicts (which use
    class names as keys after the run_series standardisation) are translated to display
    names before being posted to the TUI, so all rendering stays human-readable.
    """

    def __init__(self, n_games: int, display_names: dict[str, str] | None = None) -> None:
        self._n_games = n_games
        self._display_names: dict[str, str] = display_names or {}
        self._app: LiarsDiceApp | None = None

    def _to_display(self, wins: dict[str, int]) -> dict[str, int]:
        if not self._display_names:
            return wins
        return {self._display_names.get(k, k): v for k, v in wins.items()}

    def run(self, simulation: Callable[[], None]) -> None:
        """Start the TUI. Runs simulation in a background thread; blocks until user quits."""
        ready = threading.Event()
        self._app = LiarsDiceApp(n_games=self._n_games, ready_event=ready)

        original_stdout = sys.stdout
        log_stream = LogStream(self._app)

        def _sim_thread() -> None:
            ready.wait()
            sys.stdout = log_stream
            try:
                simulation()
            finally:
                sys.stdout = original_stdout
                self._app.call_from_thread(self._app.post_message, SimulationComplete())

        t = threading.Thread(target=_sim_thread, daemon=True)
        t.start()
        self._app.run()

    def start_step(self, label: str) -> None:
        if self._app:
            self._app.call_from_thread(self._app.post_message, StepStarted(label))

    def start_series(self, label: str) -> None:
        if self._app:
            self._app.call_from_thread(self._app.post_message, SeriesStarted(label))

    def update(self, game_num: int, wins: dict[str, int], stats) -> None:
        if self._app is None:
            return
        import copy

        self._app.call_from_thread(
            self._app.post_message,
            GameComplete(game_num, self._to_display(wins), copy.copy(stats)),
        )

    def on_series_complete(self, label: str, result) -> None:
        if self._app:
            from game.components.series import SeriesResult

            translated = SeriesResult(
                wins=self._to_display(result.wins),
                stats=result.stats,
                tier=result.tier,
                outcomes=result.outcomes,
            )
            self._app.call_from_thread(self._app.post_message, SeriesComplete(label, translated))
