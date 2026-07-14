"""Minimal v1 bot used by isolation-worker tests: always bids 2x5.

Not a real strategy — just the smallest possible player for exercising the
worker bootstrap (`game/components/isolation/worker.py`) without depending on
any player-development conventions beyond the bare `algo` contract.
"""

from game.components.bets import Bet


class AlwaysBidTwoFives:
    name = "t"

    def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):
        return Bet(2, 5, self.name)
