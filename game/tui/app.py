"""Textual app for the liars-dice live tuning dashboard."""

from __future__ import annotations

import threading

from textual.app import App, ComposeResult
from textual.containers import ScrollableContainer
from textual.events import Resize
from textual.widgets import Footer, Label, TabbedContent, TabPane

from game.tui.messages import (
    DrillInPlayer,
    GameComplete,
    LogLine,
    SeriesComplete,
    SeriesStarted,
    SimulationComplete,
    StepStarted,
)
from game.tui.simdb import SimDB
from game.tui.widgets import (
    LogPanel,
    PlayerStatsPanel,
    StandingsWidget,
)

# Minimum terminal width for stats panels to render without wrapping.
# Single-column needs ~55; two-column (with Sim Total) needs ~100.
_MIN_WIDTH = 100

_KNOWN_TIERS = {"PRM", "CH", "L1"}


def _extract_tier(label: str) -> str | None:
    """Return "PRM", "CH", or "L1" from a series label, or None for tournament pools."""
    if not label:
        return None
    first = label.split()[0].upper()
    return first if first in _KNOWN_TIERS else None


class LiarsDiceApp(App):
    """Textual TUI for live bot tuning. Receives messages from the simulation thread."""

    CSS = """
    Screen {
        layout: vertical;
    }

    TabbedContent {
        height: 1fr;
    }

    TabPane {
        layout: vertical;
        padding: 0;
        height: 1fr;
    }

    ContentSwitcher {
        height: 1fr;
    }

    StandingsWidget {
        height: auto;
        max-height: 15;
    }

    #player-panels {
        height: 1fr;
    }

    LogPanel {
        height: 10;
        dock: bottom;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("v", "toggle_verbose", "Verbose"),
        ("s", "focus_standings", "Standings"),
        ("p", "focus_panel", "Next panel"),
        ("[", "prev_outer_tab", "◀ Tab"),
        ("]", "next_outer_tab", "Tab ▶"),
        ("{", "prev_inner_tab", "◀ Step"),
        ("}", "next_inner_tab", "Step ▶"),
        ("escape", "remove_panel", "Close panel"),
    ]

    def __init__(self, n_games: int, ready_event: threading.Event) -> None:
        super().__init__()
        self._n_games = n_games
        self._ready_event = ready_event
        self._db: SimDB = SimDB()
        self._current_wins: dict[str, int] = {}
        self._current_stats = None
        self._current_game = 0
        self._current_label = ""
        self._current_tier: str | None = None
        self._current_step_label: str = ""
        self._current_step_tier_results: dict[str, tuple] = {}
        self._sim_done = False
        self._drilled: list[str] = []
        self._history_tab_count = 0
        self._step_count = 0
        self._current_step_inner_id: str | None = None
        self._outer_tab_ids: list[str] = ["live"]  # outer TabbedContent pane IDs in order
        self._inner_tab_ids: dict[str, list[str]] = {}  # inner_tc_id → hist pane IDs

    def compose(self) -> ComposeResult:
        with TabbedContent(id="tabs", initial="live"):
            with TabPane("Live", id="live"):
                yield StandingsWidget()
                yield ScrollableContainer(id="player-panels")
        yield LogPanel()
        yield Footer()

    def on_mount(self) -> None:
        self.query_one(StandingsWidget).focus()
        self.call_after_refresh(self._on_first_frame)

    def _on_first_frame(self) -> None:
        self._ready_event.set()
        self._check_width(self.size.width)

    def on_resize(self, event: Resize) -> None:
        self._check_width(event.size.width)

    def _check_width(self, width: int) -> None:
        if width < _MIN_WIDTH:
            log = self.query_one(LogPanel)
            log.write_line(
                f"[yellow]⚠ Terminal is {width} columns wide — stats panels need "
                f"{_MIN_WIDTH}+ columns to display correctly. Widen your terminal.[/yellow]"
            )

    # ── Message handlers ──────────────────────────────────────────────────

    def on_step_started(self, message: StepStarted) -> None:
        self._step_count += 1
        self._current_step_label = message.label
        self._current_step_tier_results = {}
        inner_id = f"step-tabs-{self._step_count}"
        self._current_step_inner_id = inner_id
        outer_id = f"step-{self._step_count}"
        pane = TabPane(
            message.label,
            Label("[dim]In progress — series results will appear as they complete.[/dim]"),
            TabbedContent(id=inner_id),
            id=outer_id,
        )
        self.query_one("#tabs", TabbedContent).add_pane(pane)
        self._outer_tab_ids.append(outer_id)

    def on_series_started(self, message: SeriesStarted) -> None:
        self._current_label = message.label
        self._current_tier = _extract_tier(message.label)
        self._current_wins = {}
        self._current_stats = None
        self._current_game = 0
        standings = self.query_one(StandingsWidget)
        standings.clear_standings()
        log = self.query_one(LogPanel)
        log.write_line(f"[bold]── {message.label} ──[/bold]")

    def on_game_complete(self, message: GameComplete) -> None:
        self._current_game = message.game_num
        self._current_wins = message.wins
        self._current_stats = message.stats

        standings = self.query_one(StandingsWidget)
        standings.update_standings(
            message.wins,
            message.stats,
            message.game_num,
            self._n_games,
            self._current_label,
        )

        step_tiers = self._build_step_tiers(message.wins, message.stats, message.game_num)
        for panel in self.query(PlayerStatsPanel):
            if panel.player not in message.stats.games_played:
                continue
            panel.update_step_data(step_tiers, message.wins, message.stats, message.game_num)

        log = self.query_one(LogPanel)
        if log.verbose:
            winner = max(message.wins, key=lambda p: message.wins.get(p, 0), default="?")
            log.write_line(
                f"[dim]game {message.game_num}: {winner} leads "
                f"({message.wins.get(winner, 0)} wins)[/dim]"
            )

    def on_series_complete(self, message: SeriesComplete) -> None:
        tier = message.result.tier
        if tier:
            self._current_step_tier_results[tier] = (
                message.result.wins,
                message.result.stats,
                self._n_games,
            )
        self._db.insert_series(self._current_step_label, tier, message.result)
        self._add_history_tab(message.label, message.result)
        for panel in self.query(PlayerStatsPanel):
            panel.update_aggregate(self._db.query_aggregate(panel.player))

    def on_simulation_complete(self, _: SimulationComplete) -> None:
        self._sim_done = True
        log = self.query_one(LogPanel)
        log.write_line("[bold green]Simulation complete — press q to exit[/bold green]")

    def on_log_line(self, message: LogLine) -> None:
        self.query_one(LogPanel).write_line(message.text)

    def on_drill_in_player(self, message: DrillInPlayer) -> None:
        if message.player in self._drilled:
            self._drilled.remove(message.player)
            for panel in self.query(PlayerStatsPanel):
                if panel.player == message.player:
                    panel.remove()
                    return
            return
        self._drilled.append(message.player)
        step_tiers = self._build_step_tiers(
            self._current_wins, self._current_stats, self._current_game
        )
        panel = PlayerStatsPanel(
            player=message.player,
            n_games=self._n_games,
        )
        panel.update_aggregate(self._db.query_aggregate(message.player))
        panel.update_step_data(
            step_tiers, self._current_wins, self._current_stats, self._current_game
        )
        container = self.query_one("#player-panels", ScrollableContainer)
        container.mount(panel)

    # ── Actions ───────────────────────────────────────────────────────────

    def action_quit(self) -> None:
        self.exit()

    def action_toggle_verbose(self) -> None:
        self.query_one(LogPanel).toggle_verbose()

    def action_remove_panel(self) -> None:
        if not self._drilled:
            return
        player = self._drilled.pop()
        for panel in self.query(PlayerStatsPanel):
            if panel.player == player:
                panel.remove()
                return

    def action_next_outer_tab(self) -> None:
        self._cycle_outer_tab(step=1)

    def action_prev_outer_tab(self) -> None:
        self._cycle_outer_tab(step=-1)

    def action_next_inner_tab(self) -> None:
        self._cycle_inner_tab(step=1)

    def action_prev_inner_tab(self) -> None:
        self._cycle_inner_tab(step=-1)

    def action_focus_standings(self) -> None:
        self.query_one(StandingsWidget).focus()

    def action_focus_panel(self) -> None:
        panels = list(self.query(PlayerStatsPanel))
        if not panels:
            return
        try:
            idx = panels.index(self.focused)
            panels[(idx + 1) % len(panels)].focus()
        except ValueError:
            panels[0].focus()

    # ── Internal helpers ──────────────────────────────────────────────────

    def _cycle_outer_tab(self, step: int) -> None:
        """Cycle the outer TabbedContent using the tracked list of outer pane IDs."""
        ids = self._outer_tab_ids
        if len(ids) < 2:
            return
        tc = self.query_one("#tabs", TabbedContent)
        try:
            idx = ids.index(tc.active)
        except ValueError:
            idx = 0
        new_active = ids[(idx + step) % len(ids)]
        # Move focus outside all TabPanes before switching. When the active pane
        # is hidden, Textual moves focus for whichever widget currently holds it;
        # if that widget is inside the outgoing pane, the focus event bubbles
        # through TabPane and fires _on_tab_pane_focused, which immediately
        # reverts tc.active back to the old pane. Focusing LogPanel (docked
        # outside the TabbedContent) breaks that cycle.
        self.query_one(LogPanel).focus()
        tc.active = new_active
        if new_active == "live":
            self.call_after_refresh(lambda: self.query_one(StandingsWidget).focus())

    def _cycle_inner_tab(self, step: int) -> None:
        """Cycle the inner TabbedContent for the current step using the tracked list."""
        if not self._current_step_inner_id:
            return
        ids = self._inner_tab_ids.get(self._current_step_inner_id, [])
        if len(ids) < 2:
            return
        try:
            tc = self.query_one(f"#{self._current_step_inner_id}", TabbedContent)
            try:
                idx = ids.index(tc.active)
            except ValueError:
                idx = 0
            tc.active = ids[(idx + step) % len(ids)]
        except Exception:
            pass

    def _build_step_tiers(self, wins, stats, game_num) -> dict:
        """Combine completed step tiers with the current live series."""
        step_tiers = dict(self._current_step_tier_results)
        if self._current_tier and stats is not None:
            step_tiers[self._current_tier] = (wins, stats, game_num)
        return step_tiers

    def _add_history_tab(self, label: str, result) -> None:
        """Add a history tab (or sub-tab inside current step) with final series standings."""
        self._history_tab_count += 1
        tab_id = f"hist-{self._history_tab_count}"
        widget = StandingsWidget()
        widget.update_standings(result.wins, result.stats, self._n_games, self._n_games, label)
        pane = TabPane(label, widget, id=tab_id)
        if self._current_step_inner_id:
            inner = self.query_one(f"#{self._current_step_inner_id}", TabbedContent)
            inner.add_pane(pane)
            self._inner_tab_ids.setdefault(self._current_step_inner_id, []).append(tab_id)
        else:
            self.query_one("#tabs", TabbedContent).add_pane(pane)
            self._outer_tab_ids.append(tab_id)
