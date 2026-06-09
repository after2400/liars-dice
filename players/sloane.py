from math import comb

from game.components.bets import Bet


class Sloane:
    name = "Sloane"

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

    def _calculate_delta_bias(self, player: str, face: int, outcomes: list[dict]) -> float:
        relevant = [o for o in outcomes if o["bidder"] == player and o["final_bet"].face == face]
        if not relevant:
            return 0.0
        held = sum(1 for o in relevant if o["bet_held"])
        reliability = held / len(relevant)
        return (0.5 - reliability) * 0.2

    def _calculate_delta_momentum(
        self, bet_history: list[dict], game: int, round_num: int
    ) -> float:
        round_bets = [
            b["bet"] for b in bet_history if b["game"] == game and b["round"] == round_num
        ]
        if len(round_bets) < 2:
            return 0.0
        diffs = [
            round_bets[i].quantity - round_bets[i - 1].quantity for i in range(1, len(round_bets))
        ]
        avg_velocity = sum(diffs) / len(diffs)
        return (1.0 - avg_velocity) * 0.1

    def _calculate_delta_signature(
        self, player: str, face: int, quantity: int, outcomes: list[dict]
    ) -> float:
        relevant = [
            o["final_bet"].quantity
            for o in outcomes
            if o["bidder"] == player and o["final_bet"].face == face and o["bet_held"]
        ]
        if not relevant:
            return 0.0
        mean_qty = sum(relevant) / len(relevant)
        ratio = quantity / mean_qty if mean_qty > 0 else 1.0
        if ratio > 1.5:
            return min(0.1, (ratio - 1.5) * 0.05)
        return 0.0

    def algo(
        self,
        hand: list[int],
        prior_bet: Bet | None,
        total_dice: int,
        bet_history: list[dict],
        outcomes: list[dict],
    ) -> Bet | None:
        if prior_bet is None:
            # Open round: conservative opening like Diego, slightly aggressive on strong faces
            best_face = max(range(2, 7), key=lambda f: hand.count(f) + hand.count(1))
            own = hand.count(best_face) + hand.count(1)
            unseen = total_dice - len(hand)
            expected_others = unseen * (2 / 6)
            quantity = max(1, round(own + expected_others * 0.7))
            return Bet(quantity, best_face, self.name)

        # Calculate adjusted threshold
        p_holds = self._prob_bet_holds(hand, prior_bet.face, prior_bet.quantity, total_dice)

        # We need game and round indices from bet_history to compute momentum
        # Since we don't have them explicitly in algo args, we infer from the last entry of bet_history
        if not bet_history:
            game, round_num = 0, 0
        else:
            last_entry = bet_history[-1]
            game, round_num = last_entry["game"], last_entry["round"]

        delta_bias = self._calculate_delta_bias(prior_bet.player, prior_bet.face, outcomes)
        delta_momentum = self._calculate_delta_momentum(bet_history, game, round_num)
        delta_sig = self._calculate_delta_signature(
            prior_bet.player, prior_bet.face, prior_bet.quantity, outcomes
        )

        threshold_eff = 0.30 + delta_bias + delta_momentum + delta_sig

        if p_holds < threshold_eff:
            return None  # Call liar

        # Raising strategy (Diego-style)
        own_on_face = hand.count(prior_bet.face) + (hand.count(1) if prior_bet.face != 1 else 0)
        if own_on_face > 0:
            return Bet(prior_bet.quantity + 1, prior_bet.face, self.name)

        for face in range(prior_bet.face + 1, 7):
            if hand.count(face) + hand.count(1) > 0:
                return Bet(prior_bet.quantity, face, self.name)

        return Bet(prior_bet.quantity + 1, prior_bet.face, self.name)
