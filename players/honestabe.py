from math import comb

from game.components.bets import Bet
from game.components.context import GameContext


class HonestAbe:
    """
    Honest in name only. Abe will absolutely bluff you — he's just done the
    math first. Unlike the league's other probability players (Zara, Remy,
    Nuke), who blindly assume 1s are always wild, Abe actually remembers
    whether the round opened on ones (the engine permanently revokes wild
    status for the round when it does) and grades every claim against the
    correct odds instead of vibes. When it's time to raise, he doesn't just
    bump his number and hope — he checks every legal next move and picks
    whichever lie is statistically the least likely to get him caught.
    """

    name = "Honest Abe"

    def __init__(self) -> None:
        self._bh_idx = 0
        self._round_key: tuple[int, int] | None = None
        self._wilds_active = True

    def _sync_wilds(self, bet_history) -> None:
        for i in range(self._bh_idx, len(bet_history)):
            entry = bet_history[i]
            key = (entry["game"], entry["round"])
            if key != self._round_key:
                self._round_key = key
                self._wilds_active = entry["bet"].face != 1
        self._bh_idx = len(bet_history)

    def _prob_holds(self, face: int, quantity: int, hand: list[int], total_dice: int) -> float:
        wild_bonus = self._wilds_active and face != 1
        own = hand.count(face) + (hand.count(1) if wild_bonus else 0)
        need = quantity - own
        if need <= 0:
            return 1.0
        unseen = total_dice - len(hand)
        if need > unseen:
            return 0.0
        p = 2 / 6 if wild_bonus else 1 / 6
        return sum(
            comb(unseen, k) * (p**k) * ((1 - p) ** (unseen - k)) for k in range(need, unseen + 1)
        )

    def _challenge_threshold(self, bidder: str, stats) -> float:
        bluff_rate = stats.bluff_rate.get(bidder, 0.5) if stats is not None else 0.5
        return max(0.10, min(0.50, 0.30 + (bluff_rate - 0.5) * 0.30))

    def _open(self, hand: list[int], total_dice: int) -> Bet:
        # We always open on a non-1 face, so wilds are guaranteed on this round
        # regardless of what last round left behind.
        self._wilds_active = True
        best_face = max(range(2, 7), key=lambda f: hand.count(f) + hand.count(1))
        quantity = max(1, hand.count(best_face) + hand.count(1))
        while self._prob_holds(best_face, quantity + 1, hand, total_dice) >= 0.5:
            quantity += 1
        return Bet(quantity, best_face, self.name)

    def _best_raise(self, prior_bet: Bet, hand: list[int], total_dice: int) -> Bet:
        candidates = [Bet(prior_bet.quantity, f, self.name) for f in range(prior_bet.face + 1, 7)]
        raise_faces = range(2, 7) if self._wilds_active else range(1, 7)
        candidates += [Bet(prior_bet.quantity + 1, f, self.name) for f in raise_faces]
        return max(candidates, key=lambda c: self._prob_holds(c.face, c.quantity, hand, total_dice))

    def algo(self, ctx: GameContext) -> Bet | None:
        self._sync_wilds(ctx.bet_history)

        hand = ctx.hand
        prior_bet = ctx.prior_bet
        total_dice = ctx.total_dice
        stats = ctx.stats

        if prior_bet is None:
            return self._open(hand, total_dice)

        if self._prob_holds(
            prior_bet.face, prior_bet.quantity, hand, total_dice
        ) < self._challenge_threshold(prior_bet.player, stats):
            return None

        return self._best_raise(prior_bet, hand, total_dice)
