from __future__ import annotations

from types import MappingProxyType

from game.components.stats import GameStats


class _ReadOnlySequence:
    """Read-only proxy over a shared list. Dict entries are returned as MappingProxyType.

    Wraps the live accumulator list without copying it — O(1) creation per game.
    Players cannot append, pop, or clear; dict entries cannot be mutated.
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


class GameContext:
    """Immutable per-turn game state passed to v2 algo(self, ctx) players.

    All fields are read-only. bet_history and outcomes are _ReadOnlySequence
    views over the shared live lists — no copying, O(1) creation per game.
    Dict entries are MappingProxyType: readable, not writable.
    stats is a shared GameStats instance — treat as read-only.
    """

    __slots__ = (
        "_hand",
        "_prior_bet",
        "_total_dice",
        "_bet_history",
        "_outcomes",
        "_stats",
        "_tier",
        "_round_players",
    )

    def __init__(
        self,
        hand: list[int],
        prior_bet,
        total_dice: int,
        bet_history: _ReadOnlySequence,
        outcomes: _ReadOnlySequence,
        stats: GameStats | None,
        tier: str | None,
        round_players: list[str],
    ) -> None:
        object.__setattr__(self, "_hand", tuple(hand))
        object.__setattr__(self, "_prior_bet", prior_bet)
        object.__setattr__(self, "_total_dice", total_dice)
        object.__setattr__(self, "_bet_history", bet_history)
        object.__setattr__(self, "_outcomes", outcomes)
        object.__setattr__(self, "_stats", stats if stats is not None else GameStats())
        object.__setattr__(self, "_tier", tier)
        object.__setattr__(self, "_round_players", tuple(round_players))

    def __setattr__(self, name, value):
        raise AttributeError("GameContext is read-only")

    @property
    def hand(self) -> list[int]:
        return list(self._hand)

    @property
    def prior_bet(self):
        return self._prior_bet

    @property
    def total_dice(self) -> int:
        return self._total_dice

    @property
    def bet_history(self) -> _ReadOnlySequence:
        return self._bet_history

    @property
    def outcomes(self) -> _ReadOnlySequence:
        return self._outcomes

    @property
    def stats(self) -> GameStats:
        return self._stats

    @property
    def tier(self) -> str | None:
        return self._tier

    @property
    def round_players(self) -> list[str]:
        return list(self._round_players)

    def __repr__(self) -> str:
        return (
            f"GameContext(total_dice={self._total_dice}, "
            f"prior_bet={self._prior_bet!r}, "
            f"tier={self._tier!r}, "
            f"round_players={list(self._round_players)!r})"
        )
