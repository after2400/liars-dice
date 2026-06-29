from __future__ import annotations

import sqlite3
import threading
from typing import TYPE_CHECKING

from game.components.series import SeriesResult

if TYPE_CHECKING:
    from game.tui.widgets import PlayerAggregate

_SCHEMA = """
CREATE TABLE series (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    step_label  TEXT    NOT NULL,
    tier        TEXT,
    player      TEXT    NOT NULL,
    wins        INTEGER NOT NULL,
    games       INTEGER NOT NULL,
    rounds      INTEGER NOT NULL,
    penalties   INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE h2h (
    series_id       INTEGER NOT NULL,
    player          TEXT    NOT NULL,
    opponent        TEXT    NOT NULL,
    lost_bluff      INTEGER NOT NULL DEFAULT 0,
    lost_challenge  INTEGER NOT NULL DEFAULT 0,
    won_bluff       INTEGER NOT NULL DEFAULT 0,
    won_challenge   INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE challenge_by_face (
    series_id  INTEGER NOT NULL,
    player     TEXT    NOT NULL,
    face       INTEGER NOT NULL,
    successes  INTEGER NOT NULL DEFAULT 0,
    total      INTEGER NOT NULL DEFAULT 0
);
"""


class SimDB:
    """SQLite :memory: store for completed-series stats. Thread-safe via a lock."""

    def __init__(self) -> None:
        self._conn = sqlite3.connect(":memory:", check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock:
            self._conn.executescript(_SCHEMA)

    def insert_series(self, step_label: str, tier: str | None, result: SeriesResult) -> None:
        """Insert one row per player from a completed SeriesResult into all tables."""
        stats = result.stats
        with self._lock:
            for player in stats.games_played:
                cur = self._conn.execute(
                    "INSERT INTO series (step_label, tier, player, wins, games, rounds, penalties) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        step_label,
                        tier,
                        player,
                        result.wins.get(player, 0),
                        stats.games_played.get(player, 0),
                        stats.rounds_played.get(player, 0),
                        stats.penalty_count.get(player, 0),
                    ),
                )
                series_id = cur.lastrowid

                bluff_losses = stats.die_losses_from_bluff.get(player, {})
                call_losses = stats.die_losses_from_challenge.get(player, {})
                bluff_src = stats.die_losses_from_bluff
                call_src = stats.die_losses_from_challenge
                opponents = (
                    set(bluff_losses)
                    | set(call_losses)
                    | {opp for opp, v in bluff_src.items() if player in v}
                    | {opp for opp, v in call_src.items() if player in v}
                )
                for opp in opponents:
                    self._conn.execute(
                        "INSERT INTO h2h "
                        "(series_id, player, opponent, lost_bluff, lost_challenge, won_bluff, won_challenge) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (
                            series_id,
                            player,
                            opp,
                            bluff_losses.get(opp, 0),
                            call_losses.get(opp, 0),
                            bluff_src.get(opp, {}).get(player, 0),
                            call_src.get(opp, {}).get(player, 0),
                        ),
                    )

                cs_by_face = stats.challenge_success_by_face.get(player, {})
                cc_by_face = stats.challenge_count_by_face.get(player, {})
                for face in set(cs_by_face) | set(cc_by_face):
                    self._conn.execute(
                        "INSERT INTO challenge_by_face (series_id, player, face, successes, total) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (
                            series_id,
                            player,
                            face,
                            cs_by_face.get(face, 0),
                            cc_by_face.get(face, 0),
                        ),
                    )
            self._conn.commit()

    def query_aggregate(self, player: str) -> "PlayerAggregate":
        """Return a PlayerAggregate populated from all completed series for player."""
        from game.tui.widgets import PlayerAggregate, TierStats

        agg = PlayerAggregate()
        with self._lock:
            row = self._conn.execute(
                "SELECT SUM(wins), SUM(games), SUM(rounds), SUM(penalties) "
                "FROM series WHERE player = ?",
                (player,),
            ).fetchone()
            if row and row[0] is not None:
                agg.wins = row[0]
                agg.total_games = row[1]
                agg.rounds_played = row[2]
                agg.penalties = row[3]

            for tier, wins, games, rounds in self._conn.execute(
                "SELECT tier, SUM(wins), SUM(games), SUM(rounds) "
                "FROM series WHERE player = ? AND tier IS NOT NULL GROUP BY tier",
                (player,),
            ):
                agg.per_tier[tier] = TierStats(games=games, wins=wins, rounds_played=rounds)

            for opp, lb, lc, wb, wc in self._conn.execute(
                "SELECT opponent, SUM(lost_bluff), SUM(lost_challenge), "
                "SUM(won_bluff), SUM(won_challenge) "
                "FROM h2h WHERE player = ? GROUP BY opponent",
                (player,),
            ):
                if lb:
                    agg.die_losses_from_bluff[opp] = lb
                if lc:
                    agg.die_losses_from_challenge[opp] = lc
                if wb:
                    agg.die_wins_from_bluff[opp] = wb
                if wc:
                    agg.die_wins_from_challenge[opp] = wc

            for face, succs, total in self._conn.execute(
                "SELECT face, SUM(successes), SUM(total) "
                "FROM challenge_by_face WHERE player = ? GROUP BY face",
                (player,),
            ):
                agg.challenge_success_by_face[face] = succs
                agg.challenge_total_by_face[face] = total

        return agg
