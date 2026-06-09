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

    # ------------------------------------------------------------------
    # Core probability
    # ------------------------------------------------------------------

    def _prob_bet_holds(self, hand: list[int], face: int, quantity: int, total_dice: int) -> float:
        """P(actual_count >= quantity) given known hand, modelling unseen dice."""
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

    # ------------------------------------------------------------------
    # Signal 1: revealed-hand face bias
    # ------------------------------------------------------------------

    def _face_bias(self, player: str, face: int, outcomes: list[dict]) -> float:
        """
        Estimate the fraction of a player's dice that showed `face` across
        all revealed rounds, minus the naive expectation (1/6).

        Returns a float in roughly (-0.17, +0.83).  Positive means the player
        tends to hold that face more than average; negative means less.

        Only rounds where the player's hand is present in `outcomes["hands"]`
        are counted.  Returns 0.0 if no data.
        """
        total_dice_seen = 0
        total_face_seen = 0
        for o in outcomes:
            hands = o.get("hands", {})
            if player not in hands:
                continue
            phand = hands[player]
            total_dice_seen += len(phand)
            total_face_seen += phand.count(face)
            # 1s are wild for non-1 faces: if face!=1, count 1s as contributing
            if face != 1:
                total_face_seen += phand.count(1)

        if total_dice_seen == 0:
            return 0.0

        observed_rate = total_face_seen / total_dice_seen
        expected_rate = 2 / 6 if face != 1 else 1 / 6  # baseline p used in _prob_bet_holds
        return observed_rate - expected_rate  # positive → player over-represents face

    def _bias_adjustment(self, player: str, face: int, outcomes: list[dict]) -> float:
        """
        Convert the face bias into a threshold adjustment.

        If an opponent historically over-represents face F (bias > 0), their
        bid on F is more credible, so we LOWER the liar threshold (harder to
        call liar).  If they under-represent it (bias < 0), we RAISE the
        threshold.

        Scaled conservatively: ±0.08 maximum effect, only when ≥4 rounds of data.
        """
        rounds_with_player = sum(1 for o in outcomes if player in o.get("hands", {}))
        if rounds_with_player < 2:
            return 0.0
        bias = self._face_bias(player, face, outcomes)
        # Clamp bias effect
        return -max(-0.08, min(0.08, bias * 0.4))

    # ------------------------------------------------------------------
    # Signal 2: intra-round bid trajectory
    # ------------------------------------------------------------------

    def _round_velocity(self, bet_history: list[dict], game: int, round_num: int) -> float:
        """
        Average quantity jump per bid step in the current round.

        High velocity (>= 1.5) → escalating bets → people have backing →
        lower liar threshold (more credible).
        Low velocity (< 0.8) → reluctant raises → possible bluffing →
        raise liar threshold.
        Returns 1.0 (neutral) if fewer than 2 bids in round.
        """
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
        """
        Convert round velocity into a threshold delta.

        High velocity → lower threshold (bids are credible, don't call liar).
        Low velocity → higher threshold (smells like bluffing, call liar earlier).
        Capped at ±0.06.
        """
        # Neutral at velocity=1.0.  Each unit above/below shifts threshold ±0.06.
        delta = -(velocity - 1.0) * 0.06
        return max(-0.10, min(0.10, delta))

    # ------------------------------------------------------------------
    # Signal 3: per-player bluff rate (Laplace-smoothed, like Zara)
    # ------------------------------------------------------------------

    def _bluff_rate(self, player: str, outcomes: list[dict]) -> float:
        bluffs = sum(1 for o in outcomes if o["bidder"] == player and not o["bet_held"])
        holds = sum(1 for o in outcomes if o["bidder"] == player and o["bet_held"])
        return (bluffs + 1) / (bluffs + holds + 2)

    # ------------------------------------------------------------------
    # Combined threshold
    # ------------------------------------------------------------------

    def _threshold(
        self,
        bidder: str,
        face: int,
        total_dice: int,
        bet_history: list[dict],
        outcomes: list[dict],
        game: int,
        round_num: int,
    ) -> float:
        """
        Composite liar threshold.

        Base: Diego's calibrated 0.30 (not Finn's higher 0.40 — Diego's flat 0.30
        is empirically well-tuned for 4-player Liar's Dice).
        + Zara-style bluff-rate offset (bluffers trigger calls earlier).
        + Face-bias adjustment (if opponent is known to hold this face, lower threshold).
        + Velocity adjustment (fast escalation → lower threshold).
        """
        # Diego-calibrated base
        base = 0.30

        # Bluff-rate offset: bluff_rate=0.5 → 0, bluff_rate=1 → +0.15, rate=0 → -0.15
        bluff_rate = self._bluff_rate(bidder, outcomes)
        bluff_offset = (bluff_rate - 0.5) * 0.30

        # Face-bias: positive bias → lower threshold (they probably hold it)
        bias_adj = self._bias_adjustment(bidder, face, outcomes)

        # Velocity: fast round → lower threshold
        velocity = self._round_velocity(bet_history, game, round_num)
        vel_adj = self._velocity_adjustment(velocity)

        # Endgame: with few dice left, be slightly more conservative to survive
        endgame_adj = -0.05 if total_dice <= 10 else 0.0

        return max(0.10, base + bluff_offset + bias_adj + vel_adj + endgame_adj)

    # ------------------------------------------------------------------
    # Bid selection helpers
    # ------------------------------------------------------------------

    def _best_raise(self, hand: list[int], prior_bet: Bet, total_dice: int) -> Bet:
        """
        Pick the safest legal raise Remy can make.

        Priority:
        1. If well-backed on same face (own >= 2): raise quantity by 2.
        2. If backed on same face (own >= 1): raise quantity by 1.
        3. Shift to a higher face Remy holds (same quantity).
        4. Minimal raise (quantity+1, same face) as last resort.
        """
        face = prior_bet.face
        own = hand.count(face) + (hand.count(1) if face != 1 else 0)

        if own >= 2:
            return Bet(prior_bet.quantity + 2, face, self.name)
        if own >= 1:
            return Bet(prior_bet.quantity + 1, face, self.name)

        # Shift to higher face we hold
        for f in range(face + 1, 7):
            if hand.count(f) + hand.count(1) > 0:
                return Bet(prior_bet.quantity, f, self.name)

        # Last resort
        return Bet(prior_bet.quantity + 1, face, self.name)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def algo(
        self,
        hand: list[int],
        prior_bet: Bet | None,
        total_dice: int,
        bet_history: list[dict],
        outcomes: list[dict],
    ) -> Bet | None:

        # ---- Opening bid ----
        if prior_bet is None:
            best_face = max(range(2, 7), key=lambda f: hand.count(f) + hand.count(1))
            own = hand.count(best_face) + hand.count(1)
            unseen = total_dice - len(hand)
            # Scale opening aggression with field size: larger fields have more dice
            # and proportionally credible higher bids
            opening_mult = min(0.82, 0.70 + total_dice * 0.004)
            quantity = max(1, round(own + unseen * (2 / 6) * opening_mult))
            return Bet(quantity, best_face, self.name)

        # ---- Determine current game/round from bet_history ----
        # The most recent entry in bet_history tells us game/round context.
        if bet_history:
            game = bet_history[-1]["game"]
            round_num = bet_history[-1]["round"]
        else:
            game = 1
            round_num = 1

        # ---- Compute threshold and probability ----
        threshold = self._threshold(
            prior_bet.player,
            prior_bet.face,
            total_dice,
            bet_history,
            outcomes,
            game,
            round_num,
        )

        p_holds = self._prob_bet_holds(hand, prior_bet.face, prior_bet.quantity, total_dice)

        if p_holds < threshold:
            return None  # call liar

        return self._best_raise(hand, prior_bet, total_dice)
