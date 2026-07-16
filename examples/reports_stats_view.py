"""Minimal v2 bot used by isolation-worker/readmodel stats-wiring tests.

Reports what it saw of the shared GameStats snapshot by encoding a count
into its returned bet: quantity = len(ctx.stats.dice_counts) (clamped to at
least 1, since a real Bet needs quantity >= 1). Not a real strategy -- just
enough to prove GameContext.stats was populated from the real shared-memory
stats channel (Task 7 wiring in worker.py's _build_args), not the default
empty GameStats() fallback.
"""

from game.components.bets import Bet
from game.components.context import GameContext


class ReportsStatsView:
    name = "s"

    def algo(self, ctx: GameContext) -> Bet:
        quantity = max(1, len(ctx.stats.dice_counts))
        return Bet(quantity, 3, self.name)
