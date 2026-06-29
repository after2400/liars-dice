from __future__ import annotations

import json
import sqlite3
import struct
from datetime import date, datetime
from pathlib import Path


def _to_signed64(n: int) -> int:
    return struct.unpack("q", struct.pack("Q", n))[0]


def _from_signed64(n: int) -> int:
    return struct.unpack("Q", struct.pack("q", n))[0]


_SCHEMA = """
CREATE TABLE meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE game_seed (
    week_num    INTEGER NOT NULL,
    tier        TEXT,
    series_idx  INTEGER NOT NULL,
    game_num    INTEGER NOT NULL,
    seed        INTEGER NOT NULL
);
"""


class ReplayDB:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    @classmethod
    def create(cls, path: str | Path) -> "ReplayDB":
        path = Path(path)
        if path.exists():
            path.unlink()
        conn = sqlite3.connect(str(path), check_same_thread=False)
        conn.executescript(_SCHEMA)
        conn.commit()
        return cls(conn)

    @classmethod
    def load(cls, path: str | Path) -> "ReplayDB":
        conn = sqlite3.connect(f"file:{Path(path)}?mode=ro", uri=True, check_same_thread=False)
        return cls(conn)

    def save_meta(
        self,
        mode: str,
        step_date: date,
        quarter: str,
        n_games: int,
        top_n: int,
        lb_snapshot: dict,
    ) -> None:
        entries = [
            ("mode", mode),
            ("step_date", step_date.isoformat()),
            ("quarter", quarter),
            ("n_games", str(n_games)),
            ("top_n", str(top_n)),
            ("lb_snapshot", json.dumps(lb_snapshot)),
            ("created_at", datetime.now().isoformat()),
        ]
        self._conn.executemany("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", entries)
        self._conn.commit()

    def save_standings(self, standings: dict) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
            ("original_standings", json.dumps(standings)),
        )
        self._conn.commit()

    def save_pool_results(self, pool_results: dict) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
            ("original_pool_results", json.dumps(pool_results)),
        )
        self._conn.commit()

    def save_seeds(
        self,
        week_num: int,
        tier: str | None,
        series_idx: int,
        seeds: list[int],
    ) -> None:
        self._conn.executemany(
            "INSERT INTO game_seed (week_num, tier, series_idx, game_num, seed) VALUES (?, ?, ?, ?, ?)",
            [
                (week_num, tier, series_idx, i + 1, _to_signed64(seed))
                for i, seed in enumerate(seeds)
            ],
        )
        self._conn.commit()

    def save_seed(
        self,
        week_num: int,
        tier: str | None,
        series_idx: int,
        game_num: int,
        seed: int,
    ) -> None:
        """Compatibility shim — prefer save_seeds for batch writes."""
        self.save_seeds(week_num, tier, series_idx, [seed])

    def get_meta(self) -> dict[str, str]:
        return dict(self._conn.execute("SELECT key, value FROM meta").fetchall())

    def get_seeds(self, week_num: int, tier: str | None, series_idx: int) -> list[int]:
        return [
            _from_signed64(row[0])
            for row in self._conn.execute(
                "SELECT seed FROM game_seed "
                "WHERE week_num=? AND tier IS ? AND series_idx=? "
                "ORDER BY game_num",
                (week_num, tier, series_idx),
            ).fetchall()
        ]

    def close(self) -> None:
        self._conn.close()
