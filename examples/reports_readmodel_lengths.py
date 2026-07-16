"""Minimal v2 bot used by isolation-worker/readmodel wiring tests.

Reports what it saw of the shared read-model by encoding lengths into its
returned bet: quantity = len(ctx.bet_history), face = 1 + (len(ctx.outcomes) % 6).
Not a real strategy -- just enough to prove GameContext.bet_history/outcomes
were populated from the real shared-memory read-model (Task 6 wiring in
worker.py's _build_args), not the empty-stub _ReadOnlySequence([]) fallback.
"""

from game.components.bets import Bet
from game.components.context import GameContext


class ReportsReadmodelLengths:
    name = "r"

    def algo(self, ctx: GameContext) -> Bet:
        quantity = max(1, len(ctx.bet_history))
        face = 1 + (len(ctx.outcomes) % 6)
        return Bet(quantity, face, self.name)
