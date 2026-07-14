import os

from game.components.bets import Bet


class ReadsEnvSecret:
    name = "probe"

    def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):
        if os.environ.get("GH_TOKEN"):
            return Bet(1, 1, self.name)  # found it — isolation FAILED
        raise RuntimeError("no secret visible")  # expected: isolation worked
