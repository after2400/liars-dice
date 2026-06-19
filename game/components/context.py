from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any


class _ReadOnlySequence:
    """Read-only proxy over a shared list. Dict entries are returned as MappingProxyType.

    Wraps the live accumulator list without copying it — O(1) creation per game.
    Players cannot append, pop, or clear; entries cannot be mutated.
    """

    __slots__ = ("_data",)

    def __init__(self, data: list) -> None:
        object.__setattr__(self, "_data", data)

    def __getitem__(self, idx):
        item = self._data[idx]
        return MappingProxyType(item) if isinstance(item, dict) else item

    def __len__(self) -> int:
        return len(self._data)

    def __iter__(self):
        return (MappingProxyType(x) if isinstance(x, dict) else x for x in self._data)

    def __setattr__(self, name, value):
        raise AttributeError("_ReadOnlySequence is read-only")

    def __repr__(self) -> str:
        return f"_ReadOnlySequence(len={len(self._data)})"


@dataclass(frozen=True)
class GameContext:
    """Immutable context passed to v2 algo(self, ctx) players.

    All fields always present — no opt-in or signature detection needed.
    bet_history and outcomes are read-only views; dict entries are MappingProxyType.
    stats is a shared GameStats instance — treat as read-only.
    """

    hand: list[int]
    prior_bet: Any  # Bet | None
    total_dice: int
    bet_history: _ReadOnlySequence
    outcomes: _ReadOnlySequence
    stats: Any  # GameStats
    tier: str | None
    round_players: list[str]
