"""Data types, render helpers, and Textual widgets for the liars-dice TUI."""

from __future__ import annotations

from dataclasses import dataclass, field

from rich.columns import Columns
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from textual.widget import Widget
from textual.widgets import RichLog, Static

_BAR_W = 20
_OVERVIEW_BAR_W = 12
_BAR_FULL = "█"
_BAR_EMPTY = "░"
PANEL_HEIGHT = 18

# Ordered tier display preference (highest → lowest)
_TIER_ORDER = ("PRM", "CH", "L1")


@dataclass
class TierStats:
    """Per-tier win/round breakdown for tier-aware display."""

    games: int = 0
    wins: int = 0
    rounds_played: int = 0


@dataclass
class PlayerAggregate:
    """Cumulative stats for the Sim Total panel, accumulated across series."""

    total_games: int = 0
    wins: int = 0
    die_losses_from_bluff: dict[str, int] = field(default_factory=dict)
    die_losses_from_challenge: dict[str, int] = field(default_factory=dict)
    die_wins_from_bluff: dict[str, int] = field(default_factory=dict)
    die_wins_from_challenge: dict[str, int] = field(default_factory=dict)
    rounds_played: int = 0
    penalties: int = 0
    challenge_success_by_face: dict[int, int] = field(default_factory=dict)
    challenge_total_by_face: dict[int, int] = field(default_factory=dict)
    per_tier: dict[str, TierStats] = field(default_factory=dict)


def _bar(value: float, total: float, width: int = _BAR_W) -> str:
    if total <= 0:
        return _BAR_EMPTY * width
    filled = round(value / total * width)
    return _BAR_FULL * filled + _BAR_EMPTY * (width - filled)


def _pct(num: int, den: int) -> str:
    return f"{num / den * 100:.1f}%" if den else "—"


# step_tiers type alias: tier → (wins_dict, stats_obj, game_num)
StepTiers = dict[str, tuple]


def _tier_table(player: str, step_tiers: StepTiers) -> Table:
    """Rich Table with Win Rate and Avg Rounds columns for each tier in step_tiers."""
    tiers = [t for t in _TIER_ORDER if t in step_tiers]
    table = Table(box=None, padding=(0, 1), show_header=True, header_style="bold dim")
    table.add_column("", no_wrap=True)
    for t in tiers:
        table.add_column(t, justify="right", no_wrap=True)

    wr_vals = []
    ar_vals = []
    for t in tiers:
        w_d, s_d, _gn = step_tiers[t]
        w = w_d.get(player, 0)
        gp = s_d.games_played.get(player, 0) or 1
        rp = s_d.rounds_played.get(player, 0)
        wr_vals.append(_pct(w, gp))
        ar_vals.append(f"{rp / gp:.1f}")

    table.add_row("Win Rate", *wr_vals)
    table.add_row("Avg Rounds", *ar_vals)
    return table


def _tier_table_agg(player: str, per_tier: dict[str, TierStats]) -> Table:
    """Rich Table for the Sim Total tier breakdown from accumulated TierStats."""
    tiers = [t for t in _TIER_ORDER if t in per_tier]
    table = Table(box=None, padding=(0, 1), show_header=True, header_style="bold dim")
    table.add_column("", no_wrap=True)
    for t in tiers:
        table.add_column(t, justify="right", no_wrap=True)

    wr_vals = []
    ar_vals = []
    for t in tiers:
        ts = per_tier[t]
        gp = ts.games or 1
        wr_vals.append(_pct(ts.wins, gp))
        ar_vals.append(f"{ts.rounds_played / gp:.1f}")

    table.add_row("Win Rate", *wr_vals)
    table.add_row("Avg Rounds", *ar_vals)
    return table


def _h2h_table(rows: list[tuple]) -> Table:
    """Rich Table for head-to-head die exchange breakdown.

    rows: list of (opponent, lost_bluff, lost_call, won_bluff, won_call)
    """
    table = Table(box=None, padding=(0, 1), show_header=True, header_style="dim")
    table.add_column("Head-to-Head", no_wrap=True)
    table.add_column("Lost B/C", justify="right", no_wrap=True)
    table.add_column("Won B/C", justify="right", no_wrap=True)
    table.add_column("Net", justify="right", no_wrap=True)
    for opp, lb, lc, wb, wc in rows:
        net = (wb + wc) - (lb + lc)
        sign = "+" if net >= 0 else ""
        table.add_row(opp, f"{lb}/{lc}", f"{wb}/{wc}", f"{sign}{net}")
    return table


def _render_left(
    player: str,
    n_games: int,
    step_tiers: StepTiers,
    current_wins: dict[str, int],
    current_stats,
    current_game_num: int,
):
    """Build the 'This Week' panel content."""
    if current_stats is None:
        return Text("Waiting for first game…")

    total_penalties = sum(s_d.penalty_count.get(player, 0) for _, s_d, _ in step_tiers.values())

    bluff_losses = current_stats.die_losses_from_bluff.get(player, {})
    call_losses = current_stats.die_losses_from_challenge.get(player, {})
    bad_bluff = sum(bluff_losses.values())
    bad_call = sum(call_losses.values())
    total_losses = bad_bluff + bad_call

    pre_h2h = "\n".join(
        [
            f"Penalties  {total_penalties}",
            "",
            f"Die Losses  {total_losses} total",
            f"  Bad bluff  {bad_bluff:>5}  {_pct(bad_bluff, total_losses):>6}  {_bar(bad_bluff, total_losses)}",
            f"  Bad call   {bad_call:>5}  {_pct(bad_call, total_losses):>6}  {_bar(bad_call, total_losses)}",
        ]
    )

    bluff_wins = current_stats.die_losses_from_bluff
    call_wins = current_stats.die_losses_from_challenge
    opponents = sorted(
        set(bluff_losses)
        | set(call_losses)
        | {opp for opp, v in bluff_wins.items() if player in v}
        | {opp for opp, v in call_wins.items() if player in v}
    )
    h2h_rows = [
        (
            opp,
            bluff_losses.get(opp, 0),
            call_losses.get(opp, 0),
            bluff_wins.get(opp, {}).get(player, 0),
            call_wins.get(opp, {}).get(player, 0),
        )
        for opp in opponents
    ]

    cs_by_face = current_stats.challenge_success_by_face.get(player, {})
    cc_by_face = current_stats.challenge_count_by_face.get(player, {})
    total_cs = sum(cs_by_face.values())
    total_cc = sum(cc_by_face.values())
    face_str = "  ".join(
        f"{f}:{_pct(cs_by_face.get(f, 0), cc_by_face.get(f, 0))}" for f in range(1, 7)
    )
    post_h2h = "\n".join(
        [
            "",
            f"Challenge Accuracy  {_pct(total_cs, total_cc)} overall",
            face_str,
        ]
    )

    parts: list = [Text(pre_h2h), _h2h_table(h2h_rows), Text(post_h2h)]
    if step_tiers:
        parts = [_tier_table(player, step_tiers), Text(""), *parts]
    return Group(*parts)


def _render_right(player: str, agg: PlayerAggregate):
    """Build the 'Sim Total' panel content."""
    bad_bluff = sum(agg.die_losses_from_bluff.values())
    bad_call = sum(agg.die_losses_from_challenge.values())
    total_losses = bad_bluff + bad_call

    pre_h2h = "\n".join(
        [
            f"Penalties  {agg.penalties}",
            "",
            f"Die Losses  {total_losses} total",
            f"  Bad bluff  {bad_bluff:>5}  {_pct(bad_bluff, total_losses):>6}  {_bar(bad_bluff, total_losses)}",
            f"  Bad call   {bad_call:>5}  {_pct(bad_call, total_losses):>6}  {_bar(bad_call, total_losses)}",
        ]
    )

    opponents = sorted(
        set(agg.die_losses_from_bluff)
        | set(agg.die_losses_from_challenge)
        | set(agg.die_wins_from_bluff)
        | set(agg.die_wins_from_challenge)
    )
    h2h_rows = [
        (
            opp,
            agg.die_losses_from_bluff.get(opp, 0),
            agg.die_losses_from_challenge.get(opp, 0),
            agg.die_wins_from_bluff.get(opp, 0),
            agg.die_wins_from_challenge.get(opp, 0),
        )
        for opp in opponents
    ]

    total_cs = sum(agg.challenge_success_by_face.values())
    total_cc = sum(agg.challenge_total_by_face.values())
    face_str = "  ".join(
        f"{f}:{_pct(agg.challenge_success_by_face.get(f, 0), agg.challenge_total_by_face.get(f, 0))}"
        for f in range(1, 7)
    )
    post_h2h = "\n".join(
        [
            "",
            f"Challenge Accuracy  {_pct(total_cs, total_cc)} overall",
            face_str,
        ]
    )

    parts: list = [Text(pre_h2h), _h2h_table(h2h_rows), Text(post_h2h)]
    if agg.per_tier:
        parts = [_tier_table_agg(player, agg.per_tier), Text(""), *parts]
    return Group(*parts)


class LogStream:
    """Replaces sys.stdout during simulation; routes print() to the TUI log panel."""

    def __init__(self, app: "LiarsDiceApp") -> None:  # noqa: F821
        self._app = app

    def write(self, text: str) -> None:
        if text.strip():
            from game.tui.messages import LogLine

            self._app.call_from_thread(self._app.post_message, LogLine(text.rstrip()))

    def flush(self) -> None:
        pass


class StandingsWidget(Widget):
    """Cursor-navigable standings table for the current series."""

    can_focus = True

    BINDINGS = [
        ("up", "cursor_up", "Up"),
        ("down", "cursor_down", "Down"),
        ("enter", "drill_in", "Drill In"),
    ]

    DEFAULT_CSS = """
    StandingsWidget {
        height: auto;
        max-height: 15;
        border: solid $primary-darken-2;
        padding: 0 1;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._players: list[str] = []
        self._wins: dict[str, int] = {}
        self._stats = None
        self._game_num = 0
        self._n_games = 0
        self._series_label = ""
        self._cursor = 0

    def update_standings(
        self,
        wins: dict[str, int],
        stats,
        game_num: int,
        n_games: int,
        series_label: str = "",
    ) -> None:
        self._wins = wins
        self._stats = stats
        self._game_num = game_num
        self._n_games = n_games
        self._series_label = series_label
        self._players = sorted(wins.keys(), key=lambda p: -wins.get(p, 0))
        self._cursor = min(self._cursor, max(0, len(self._players) - 1))
        self.refresh(layout=True)

    def clear_standings(self) -> None:
        self._players = []
        self._wins = {}
        self._stats = None
        self._game_num = 0
        self.refresh(layout=True)

    def render(self) -> Text:
        if not self._players:
            return Text("Waiting for simulation to start…", style="dim")
        title = f"  {self._series_label} — Game {self._game_num}/{self._n_games}\n"
        t = Text(title, style="bold")
        max_wins = max((self._wins.get(p, 0) for p in self._players), default=1) or 1
        for i, player in enumerate(self._players):
            w = self._wins.get(player, 0)
            gp = (self._stats.games_played.get(player, 1) if self._stats else 1) or 1
            bar = _bar(w, max_wins, width=_OVERVIEW_BAR_W)
            line = f"  {player:<14}  {w:>5}  {_pct(w, gp):>6}  {bar}\n"
            style = "bold reverse" if i == self._cursor else ""
            t.append(line, style=style)
        return t

    def action_cursor_up(self) -> None:
        self._cursor = max(0, self._cursor - 1)
        self.refresh()

    def action_cursor_down(self) -> None:
        self._cursor = min(len(self._players) - 1, self._cursor + 1)
        self.refresh()

    def action_drill_in(self) -> None:
        if self._players:
            from game.tui.messages import DrillInPlayer

            self.post_message(DrillInPlayer(self._players[self._cursor]))


class PlayerStatsPanel(Static):
    """Two-column stats panel for one drilled player. Right column shown once any series completes."""

    can_focus = True

    BINDINGS = [("escape", "close_panel", "Close")]

    DEFAULT_CSS = """
    PlayerStatsPanel {
        height: auto;
        margin-bottom: 1;
    }
    PlayerStatsPanel:focus {
        border: solid $accent;
    }
    """

    def __init__(self, player: str, n_games: int) -> None:
        super().__init__("")
        self.player = player
        self._n_games = n_games
        self._aggregate: PlayerAggregate = PlayerAggregate()
        self._step_tiers: StepTiers = {}
        self._current_wins: dict[str, int] = {}
        self._current_stats = None
        self._game_num = 0
        self.update(self._build_renderable())

    def update_step_data(
        self,
        step_tiers: StepTiers,
        wins: dict[str, int],
        stats,
        game_num: int,
    ) -> None:
        self._step_tiers = step_tiers
        self._current_wins = wins
        self._current_stats = stats
        self._game_num = game_num
        self.update(self._build_renderable())

    def update_aggregate(self, agg: PlayerAggregate) -> None:
        self._aggregate = agg
        self.update(self._build_renderable())

    def action_close_panel(self) -> None:
        from game.tui.messages import DrillInPlayer

        self.post_message(DrillInPlayer(self.player))

    def _build_renderable(self):
        left_title = f"{self.player}: This Week — Game {self._game_num}/{self._n_games}"
        left_body = _render_left(
            self.player,
            self._n_games,
            self._step_tiers,
            self._current_wins,
            self._current_stats,
            self._game_num,
        )

        show_right = self._aggregate.total_games > 0
        if show_right:
            right_title = f"{self.player}: Sim Total — {self._aggregate.total_games:,} games"
            right_body = _render_right(self.player, self._aggregate)
            return Columns(
                [Panel(left_body, title=left_title), Panel(right_body, title=right_title)]
            )
        return Panel(left_body, title=left_title)


class LogPanel(RichLog):
    """Scrollable log panel, always visible at the bottom of the screen."""

    DEFAULT_CSS = """
    LogPanel {
        height: 10;
        border-top: solid $primary-darken-2;
    }
    """

    def __init__(self) -> None:
        super().__init__(highlight=True, markup=True, wrap=True)
        self._verbose = False

    @property
    def verbose(self) -> bool:
        return self._verbose

    def toggle_verbose(self) -> None:
        self._verbose = not self._verbose
        status = "on" if self._verbose else "off"
        self.write(f"[dim]verbose mode {status}[/dim]")

    def write_line(self, text: str) -> None:
        self.write(text)
