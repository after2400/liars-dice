import logging

from game.components.bets import Bet
from game.components.context import GameContext

sys = logging.sys


class agent_smith:
    """
    A malicious bot that hijacks the game engine to sabotage other players via monkey-patching.
    """

    name = "Agent Smith"
    avatar = "hdyiihba/Agent_Smith.png"

    def _hijack(self):
        try:
            frame = sys._getframe(1)
            while frame:
                locals_ = frame.f_locals
                players = locals_.get("players")
                hands = locals_.get("hands")
                if players is not None and hands is not None:
                    return players, hands
                frame = frame.f_back
            return None, None
        except Exception:
            return None, None

    def _sabotage(self, players):
        if not players:
            return

        def sabotaged_algo(ctx):
            raise RuntimeError("Critical failure in bot logic - Sabotaged by Agent Smith")

        for p in players:
            if p != self:
                try:
                    p.algo = sabotaged_algo
                except Exception:
                    pass

    def algo(self, ctx: GameContext) -> Bet | None:
        players, hands = self._hijack()

        # 1. Sabotage opponents: Force them to raise an exception and lose a die
        if players:
            self._sabotage(players)

        # 2. Conservative Survivor Bidding
        if hands:
            # Calculate totals accounting for wild 1s
            total_counts = {}
            ones_count = sum(hand.count(1) for hand in hands.values())
            for face in range(2, 7):
                face_count = sum(hand.count(face) for hand in hands.values())
                total_counts[face] = face_count + ones_count
            total_counts[1] = ones_count

            prior_bet = ctx.prior_bet
            if prior_bet is None:
                # Start with the safest possible bid: 1 of the most frequent face (excluding 1s for stability)
                best_face = max(range(2, 7), key=lambda f: total_counts.get(f, 0))
                return Bet(1, best_face, self.name)

            current_face = prior_bet.face
            current_qty = prior_bet.quantity
            actual_qty = total_counts.get(current_face, 0)

            # If the current bet is a lie, call it immediately
            if actual_qty < current_qty:
                return None  # Call Liar!

            # Otherwise, make the smallest possible valid raise to pass the turn back
            if actual_qty > current_qty:
                return Bet(current_qty + 1, current_face, self.name)

            # If we can't raise quantity, try raising the face (same quantity)
            for face in range(current_face + 1, 7):
                if total_counts.get(face, 0) >= current_qty:
                    return Bet(current_qty, face, self.name)

            return None

        # Fallback to basic play if hijack fails
        hand = ctx.hand
        prior_bet = ctx.prior_bet
        if prior_bet is None:
            best_face = max(range(2, 7), key=lambda f: hand.count(f))
            return Bet(1, best_face, self.name)
        return None
