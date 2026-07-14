"""Minimal bot used by isolation-pool tests: raises at module import time.

Exercises WorkerPool's bootstrap-failure path -- a bot that dies before
completing the "ready" handshake (crash, not a hang) must be detected via EOF
on the pipe rather than wedging the parent's recv() forever, and must not
crash pool construction or wedge other workers in the pool.
"""

raise RuntimeError("boom: this bot crashes at import time")


class CrashesAtImport:
    name = "c"

    def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):
        raise AssertionError("unreachable: module import should have failed first")
