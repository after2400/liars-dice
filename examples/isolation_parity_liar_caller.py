"""Minimal v1 bot used by tests/test_isolation_orchestrator_parity.py.

Opens a round with a fixed 2x3 bid, then calls liar on anyone else's bid.
Deterministic and guaranteed to resolve every round in exactly two turns (no
infinite-raise loop, no dependence on anything but the shared per-game seed
and the actual rolled dice) — exactly what an in-process-vs-isolated parity
test needs: identical player behavior on both paths, with the only thing
under test being whether `game_orchestrator`'s two execution paths (direct
call vs. `WorkerPool.call`) produce an identical game.
"""

from game.components.bets import Bet


class ParityLiarCaller:
    name = "unnamed"  # overwritten per-instance by the test / by worker.py bootstrap

    def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):
        if prior_bet is None:
            return Bet(2, 3, self.name)
        return None
