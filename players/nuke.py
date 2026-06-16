import random
from math import comb

from game.components.bets import Bet


class Nuke:
    name = "Nuke LaLoosh"

    FASTBALL_PROB = 0.50
    FASTBALL_HOLD_THRESHOLD = 0.40
    BLUFF_CALL_THRESHOLD = 0.30
    DESPERATE_BUCKET_OFFSET = 0.10  # bidder has 1-2 dice: more likely bluffing
    COMFORTABLE_BUCKET_OFFSET = 0.05  # bidder has 3+ dice: less likely bluffing

    _OPENING_MULTIPLIER = {"L1": 0.85, "CH": 0.82, "PRM": 0.78}

    def __init__(self) -> None:
        self._opp: dict[str, dict] = {}
        self._last_outcomes_len: int = 0
        self._last_bet_history_len: int = 0

    def _ingest(self, outcomes: list[dict], bet_history: list[dict]) -> None:
        for o in outcomes[self._last_outcomes_len :]:
            if "bidder" not in o:
                continue
            bidder = o["bidder"]
            face = o["final_bet"].face
            d = self._opp.setdefault(
                bidder, {"bluffs": 0, "holds": 0, "face_bluffs": {}, "face_holds": {}}
            )
            if o["bet_held"]:
                d["holds"] += 1
                d["face_holds"][face] = d["face_holds"].get(face, 0) + 1
            else:
                d["bluffs"] += 1
                d["face_bluffs"][face] = d["face_bluffs"].get(face, 0) + 1
        self._last_outcomes_len = len(outcomes)

        for entry in bet_history[self._last_bet_history_len :]:
            player = entry.get("player")
            dice_count = entry.get("dice_count")
            if player is None or dice_count is None:
                continue
            d = self._opp.setdefault(
                player, {"bluffs": 0, "holds": 0, "face_bluffs": {}, "face_holds": {}}
            )
            d["last_dice_count"] = dice_count
        self._last_bet_history_len = len(bet_history)

    def _crash_davis_called_pitch(self, bidder: str, face: int) -> float:
        base = self.BLUFF_CALL_THRESHOLD
        d = self._opp.get(bidder)
        if d is None:
            return base
        bluffs, holds = d["bluffs"], d["holds"]
        bluff_rate = (bluffs + 1) / (bluffs + holds + 2)
        bluff_offset = (bluff_rate - 0.5) * 0.15
        face_bluffs = d["face_bluffs"].get(face, 0)
        face_holds = d["face_holds"].get(face, 0)
        face_bluff_rate = (face_bluffs + 1) / (face_bluffs + face_holds + 2)
        face_offset = (face_bluff_rate - 0.5) * 0.10
        last_dc = d.get("last_dice_count")
        if last_dc is not None and last_dc <= 2:
            bucket_offset = self.DESPERATE_BUCKET_OFFSET
        elif last_dc is not None:
            bucket_offset = -self.COMFORTABLE_BUCKET_OFFSET
        else:
            bucket_offset = 0.0
        return max(0.10, min(0.50, base + bluff_offset + face_offset + bucket_offset))

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

    def _fastball_eligible(self, hand: list[int]) -> bool:
        return bool(hand.count(1))

    def algo(
        self,
        hand: list[int],
        prior_bet: Bet | None,
        total_dice: int,
        bet_history: list[dict],
        outcomes: list[dict],
        tier: str | None = None,
    ) -> Bet | None:
        self._ingest(outcomes, bet_history)
        if prior_bet is None:
            if (
                tier != "PRM"
                and random.random() < self.FASTBALL_PROB
                and self._fastball_eligible(hand)
            ):
                own_1s = hand.count(1)
                unseen = total_dice - len(hand)
                quantity = max(own_1s + 1, round(own_1s + unseen * (1 / 6) * 0.7))
                return Bet(quantity, 1, self.name)
            multiplier = self._OPENING_MULTIPLIER.get(tier, 0.82) if tier else 0.82
            best_face = max(range(2, 7), key=lambda f: hand.count(f) + hand.count(1))
            own = hand.count(best_face) + hand.count(1)
            unseen = total_dice - len(hand)
            quantity = max(1, round(own + unseen * (2 / 6) * multiplier))
            return Bet(quantity, best_face, self.name)

        if self._prob_bet_holds(
            hand, prior_bet.face, prior_bet.quantity, total_dice
        ) < self._crash_davis_called_pitch(prior_bet.player, prior_bet.face):
            return None

        if (
            prior_bet.face == 1
            and tier != "PRM"
            and self._prob_bet_holds(hand, 1, prior_bet.quantity, total_dice)
            >= self.FASTBALL_HOLD_THRESHOLD
        ):
            return Bet(prior_bet.quantity + 1, 1, self.name)

        if hand.count(prior_bet.face) + (hand.count(1) if prior_bet.face != 1 else 0) > 0:
            candidate = Bet(prior_bet.quantity + 1, prior_bet.face, self.name)
        else:
            candidate = None
            for face in range(prior_bet.face + 1, 7):
                if hand.count(face) + hand.count(1) > 0:
                    candidate = Bet(prior_bet.quantity, face, self.name)
                    break
            if candidate is None:
                candidate = Bet(prior_bet.quantity + 1, prior_bet.face, self.name)

        return candidate
