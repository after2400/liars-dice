from __future__ import annotations

from math import comb

from game.components.bets import Bet
from game.components.context import GameContext


class Columbo:
    """
    Just one more thing — who opened, and why *that* face?

    Columbo appears to be fumbling through the round like he can't find his
    notepad. He is not fumbling. He already clocked the opener's first bid,
    back-solved their likely holding, and quietly steered every subsequent
    raise away from the faces they're strong on. By the time he says "liar,"
    he's known for three bets.

    Mechanics:
    - Infers opener strength by back-solving their bid quantity against their
      dice count (~70% of expected is a normal opener — anything above signals
      real backing).
    - Penalises those faces when choosing what to raise on.
    - Tracks wild-state per round (1s stop being wild once bid — most players
      forget this; Columbo does not).
    - Blends the caller's bluff rate into a per-opponent call threshold.
    """

    name = "Columbo"

    def algo(self, ctx: GameContext) -> Bet | None:
        hand = ctx.hand
        prior = ctx.prior_bet
        total = ctx.total_dice
        stats = ctx.stats

        wilds_on = self._wilds_active(ctx)
        face_strength = self._infer_opener(ctx)

        if prior is None:
            return self._open(hand, total, wilds_on, face_strength)

        p = self._hold_prob(prior.face, prior.quantity, hand, total, wilds_on)
        bluff_rate = stats.bluff_rate.get(prior.player, 0.5)
        threshold = max(0.15, min(0.45, 0.28 + (bluff_rate - 0.5) * 0.28))

        if p < threshold:
            return None  # "I think you're lying, sir. Sorry to bother you."

        return self._raise(prior, hand, total, wilds_on, face_strength)

    def _wilds_active(self, ctx: GameContext) -> bool:
        if not ctx.bet_history:
            return True
        last = ctx.bet_history[-1]
        g, r = last["game"], last["round"]
        # Did anyone bid on 1s this round? That kills wild status permanently.
        return not any(
            h["bet"].face == 1 for h in ctx.bet_history if h["game"] == g and h["round"] == r
        )

    def _infer_opener(self, ctx: GameContext) -> dict[int, float]:
        """Back-solve the opener's likely holding from their first bid."""
        if not ctx.bet_history:
            return {}

        last = ctx.bet_history[-1]
        g, r = last["game"], last["round"]
        round_bids = [h for h in ctx.bet_history if h["game"] == g and h["round"] == r]
        opener = round_bids[0]

        # Can't infer from our own bid; 1s bids are too messy to model here.
        if opener["player"] == self.name or opener["bet"].face == 1:
            return {}

        face = opener["bet"].face
        qty = opener["bet"].quantity
        dice_count = opener["dice_count"]

        # Normal openers bid ~70% of expected. More than that means backing.
        inferred = min(qty / 0.70, float(dice_count))
        expected_by_chance = dice_count / 6.0

        signal = max(0.0, inferred - expected_by_chance)
        return {face: signal * 0.5}

    def _open(self, hand, total, wilds_on, face_strength):
        unseen = total - len(hand)

        def true_expected(f):
            my = hand.count(f) + (hand.count(1) if f != 1 and wilds_on else 0)
            p = (2 / 6) if (f != 1 and wilds_on) else (1 / 6)
            return my + unseen * p

        # Prefer faces Columbo personally holds; avoid faces the opener telegraphed.
        def face_score(f):
            return true_expected(f) - face_strength.get(f, 0.0) * 0.5

        best = max(range(2, 7), key=face_score)
        qty = max(1, int(true_expected(best) * 0.70))
        return Bet(qty, best, self.name)

    def _raise(self, prior, hand, total, wilds_on, face_strength):
        face, qty = prior.face, prior.quantity

        # Quantity bump on same face, or same quantity on a higher face.
        candidates = [(qty + 1, face)]
        for f in range(face + 1, 7):
            candidates.append((qty, f))

        def score(q, f):
            p = self._hold_prob(f, q, hand, total, wilds_on)
            # Opponents strong on a face can escalate it cheaply — steer away.
            penalty = face_strength.get(f, 0.0) / max(total, 1) * 0.4
            return p - penalty

        valid = [(q, f) for q, f in candidates if 1 <= q <= total]
        if not valid:
            return Bet(qty + 1, face, self.name)

        bq, bf = max(valid, key=lambda qf: score(*qf))
        return Bet(bq, bf, self.name)

    def _hold_prob(self, face, quantity, hand, total, wilds_on) -> float:
        my = hand.count(face)
        if face != 1 and wilds_on:
            my += hand.count(1)
        need = quantity - my
        unseen = total - len(hand)
        if need <= 0:
            return 1.0
        if need > unseen:
            return 0.0
        p = (2 / 6) if (face != 1 and wilds_on) else (1 / 6)
        return sum(
            comb(unseen, k) * (p**k) * ((1 - p) ** (unseen - k)) for k in range(need, unseen + 1)
        )
