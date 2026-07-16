"""Minimal v1 bot used by isolation-pool tests: never returns.

Exercises WorkerPool's forced-kill timeout path (invariant P3) — a bot that
spins forever must still be reclaimed via external process kill(), not
cooperative cancellation.
"""


class HangsForever:
    name = "h"

    def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):
        while True:
            pass
