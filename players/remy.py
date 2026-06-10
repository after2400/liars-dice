from math import comb

from game.components.bets import Bet


class Remy:
    """
    Revealed-hand opponent modeling strategy.

    Remy exploits two signals that Diego, Finn, Eva, and Zara all ignore:

    1. Revealed hands from `outcomes["hands"]`: every past round's full dice
       are ground truth.  Remy computes a per-player, per-face "density bias"
       — how many more (or fewer) dice of each face that player actually showed
       compared to the uniform expectation.  When an opponent bids on a face
       they historically over-represent, the bid is more credible; when they
       bid on a face they rarely showed, it looks like a bluff.  The bias
       adjusts the effective probability used for the liar/raise decision.

    2. Intra-round bid trajectory from `bet_history`: if the quantity has been
       escalating fast (average jump ≥ 1.5/step), someone has backing and bids
       are more credible.  Slow minimum-raise sequences signal forced bluffing
       and widen the liar window.

    The baseline liar threshold also scales with dice remaining (like Finn) and
    with the bidder's overall bluff rate (Laplace-smoothed, like Zara).
    """

    name = "Remy"

    def _prob_bet_holds(self, hand: list[int], face: int, quantity: int, total_dice: int) -> float:
        own = hand.count(face) + (hand.count(1) if face != 1 else 0)
        unseen = total_dice - len(hand)
        p = 1 / 6 if face == 1 else 2 / 6
        need = quantity - own
        if need <= 0:
            return 1.0
        if need > unseen:
            return 0.0
        return sum(
            comb(unseen, k) * (p**k) * ((1 - p) ** (unseen - k)) for k in range(need, unseen + 1)
        )

    def _face_bias(self, player: str, face: int, outcomes: list[dict]) -> float:
        total_dice_seen = 0
        total_face_seen = 0
        for o in outcomes:
            hands = o.get("hands", {})
            if player not in hands:
                continue
            phand = hands[player]
            total_dice_seen += len(phand)
            total_face_seen += phand.count(face)
            if face != 1:
                total_face_seen += phand.count(1)
        if total_dice_seen == 0:
            return 0.0
        observed_rate = total_face_seen / total_dice_seen
        expected_rate = 2 / 6 if face != 1 else 1 / 6
        return observed_rate - expected_rate

    def _bias_adjustment(self, player: str, face: int, outcomes: list[dict]) -> float:
        rounds_with_player = sum(1 for o in outcomes if player in o.get("hands", {}))
        if rounds_with_player < 2:
            return 0.0
        bias = self._face_bias(player, face, outcomes)
        return -max(-0.08, min(0.08, bias * 0.4))

    def _bias_adjustment_from_stats(self, player: str, face: int, stats) -> float:
        if stats.rounds_with_hand.get(player, 0) < 2:
            return 0.0
        freq = stats.revealed_hand_frequency.get(player, {})
        # For non-1 faces, 1s are wild — add the 1-fraction to match _face_bias behavior.
        if face != 1:
            observed_rate = freq.get(face, 0.0) + freq.get(1, 0.0)
        else:
            observed_rate = freq.get(face, 0.0)
        expected_rate = 2 / 6 if face != 1 else 1 / 6
        bias = observed_rate - expected_rate
        return -max(-0.08, min(0.08, bias * 0.4))

    def _round_velocity(self, bet_history: list[dict], game: int, round_num: int) -> float:
        round_bets = [
            b["bet"] for b in bet_history if b["game"] == game and b["round"] == round_num
        ]
        if len(round_bets) < 2:
            return 1.0
        jumps = [
            round_bets[i].quantity - round_bets[i - 1].quantity for i in range(1, len(round_bets))
        ]
        return sum(jumps) / len(jumps)

    def _velocity_adjustment(self, velocity: float) -> float:
        delta = -(velocity - 1.0) * 0.06
        return max(-0.10, min(0.10, delta))

    def _bluff_rate(self, player: str, outcomes: list[dict]) -> float:
        bluffs = sum(1 for o in outcomes if o["bidder"] == player and not o["bet_held"])
        holds = sum(1 for o in outcomes if o["bidder"] == player and o["bet_held"])
        return (bluffs + 1) / (bluffs + holds + 2)

    def _threshold(
        self,
        bidder: str,
        face: int,
        total_dice: int,
        bet_history: list[dict],
        outcomes: list[dict],
        game: int,
        round_num: int,
        stats=None,
    ) -> float:
        base = 0.30

        if stats is not None:
            bluff_rate = stats.bluff_rate.get(bidder, 0.5)
            bias_adj = self._bias_adjustment_from_stats(bidder, face, stats)
            vel_adj = self._velocity_adjustment(stats.current_round_velocity)
        else:
            bluff_rate = self._bluff_rate(bidder, outcomes)
            bias_adj = self._bias_adjustment(bidder, face, outcomes)
            velocity = self._round_velocity(bet_history, game, round_num)
            vel_adj = self._velocity_adjustment(velocity)

        bluff_offset = (bluff_rate - 0.5) * 0.30
        endgame_adj = -0.05 if total_dice <= 10 else 0.0
        return max(0.10, base + bluff_offset + bias_adj + vel_adj + endgame_adj)

    def _best_raise(self, hand: list[int], prior_bet: Bet, total_dice: int) -> Bet:
        face = prior_bet.face
        own = hand.count(face) + (hand.count(1) if face != 1 else 0)
        if own >= 2:
            return Bet(prior_bet.quantity + 2, face, self.name)
        if own >= 1:
            return Bet(prior_bet.quantity + 1, face, self.name)
        for f in range(face + 1, 7):
            if hand.count(f) + hand.count(1) > 0:
                return Bet(prior_bet.quantity, f, self.name)
        return Bet(prior_bet.quantity + 1, face, self.name)

    def algo(
        self,
        hand: list[int],
        prior_bet: Bet | None,
        total_dice: int,
        bet_history: list[dict],
        outcomes: list[dict],
        stats=None,
    ) -> Bet | None:
        if prior_bet is None:
            best_face = max(range(2, 7), key=lambda f: hand.count(f) + hand.count(1))
            own = hand.count(best_face) + hand.count(1)
            unseen = total_dice - len(hand)
            opening_mult = min(0.82, 0.70 + total_dice * 0.004)
            quantity = max(1, round(own + unseen * (2 / 6) * opening_mult))
            return Bet(quantity, best_face, self.name)

        if bet_history:
            game = bet_history[-1]["game"]
            round_num = bet_history[-1]["round"]
        else:
            game = 1
            round_num = 1

        threshold = self._threshold(
            prior_bet.player,
            prior_bet.face,
            total_dice,
            bet_history,
            outcomes,
            game,
            round_num,
            stats=stats,
        )

        p_holds = self._prob_bet_holds(hand, prior_bet.face, prior_bet.quantity, total_dice)

        if p_holds < threshold:
            return None

        return self._best_raise(hand, prior_bet, total_dice)
