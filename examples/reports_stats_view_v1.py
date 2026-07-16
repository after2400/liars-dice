"""Minimal legacy (v1) bot used by isolation-worker stats-wiring tests.

Opts into stats by naming a `stats` parameter, per the legacy convention
(mirrors game/components/script.py's `_wants_stats` detection: `"stats" in
inspect.signature(algo).parameters`). Reports len(stats.dice_counts) the same
way examples/reports_stats_view.py does for v2, so the same assertion works
regardless of whether the worker built a GameContext or passed stats as a
kwarg.
"""

from game.components.bets import Bet


class ReportsStatsViewV1:
    name = "s1"

    def algo(self, hand, prior_bet, total_dice, bet_history, outcomes, stats=None):
        quantity = max(1, len(stats.dice_counts)) if stats is not None else 1
        return Bet(quantity, 3, self.name)
