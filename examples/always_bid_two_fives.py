"""Minimal v2 bot used by isolation-worker tests: always bids 2x5.

Not a real strategy — just the smallest possible player for exercising the
worker bootstrap (`game/components/isolation/worker.py`) without depending on
any player-development conventions beyond the bare `algo` contract.
"""

from game.components.bets import Bet
from game.components.context import GameContext


class AlwaysBidTwoFives:
    name = "t"

    def algo(self, ctx: GameContext) -> Bet:
        return Bet(2, 5, self.name)
