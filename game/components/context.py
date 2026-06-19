from __future__ import annotations

from game.components.stats import GameStats


class GameContext:
    """Immutable per-turn game state passed to v2 algo() implementations.

    All fields are read-only. List fields return a fresh mutable copy on each
    access — mutations stay local to the caller.
    History entries are MappingProxyType: dict keys are readable, not writable.
    """

    def __init__(
        self,
        hand: list[int],
        prior_bet,
        total_dice: int,
        bet_history: list,
        outcomes: list,
        stats: GameStats | None,
        tier: str | None,
        round_players: list[str],
    ) -> None:
        self.__hand = tuple(hand)
        self.__prior_bet = prior_bet
        self.__total_dice = total_dice
        self.__bet_history = tuple(bet_history)
        self.__outcomes = tuple(outcomes)
        self.__stats = stats if stats is not None else GameStats()
        self.__tier = tier
        self.__round_players = tuple(round_players)

    @property
    def hand(self) -> list[int]:
        return list(self.__hand)

    @property
    def prior_bet(self):
        return self.__prior_bet

    @property
    def total_dice(self) -> int:
        return self.__total_dice

    @property
    def bet_history(self) -> list:
        return list(self.__bet_history)

    @property
    def outcomes(self) -> list:
        return list(self.__outcomes)

    @property
    def stats(self) -> GameStats:
        return self.__stats

    @property
    def tier(self) -> str | None:
        return self.__tier

    @property
    def round_players(self) -> list[str]:
        return list(self.__round_players)

    def __repr__(self) -> str:
        return (
            f"GameContext(total_dice={self.__total_dice}, "
            f"prior_bet={self.__prior_bet!r}, "
            f"tier={self.__tier!r}, "
            f"round_players={list(self.__round_players)!r})"
        )
