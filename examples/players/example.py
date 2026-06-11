from game.components.bets import Bet


class Example:
    """A template player you can copy to start writing your own algorithm.

    This file is intentionally over-commented: it documents the whole player
    contract in one place. To make your own player, copy it to
    `players/<yourname>.py`, rename the class to match the filename
    (case-insensitive), and rewrite the body of `algo`.

    The contract:
      - Your class name MUST match its filename (e.g. `players/fred.py` ->
        `class Fred`). The leaderboard is keyed by class name, so it has to be
        unique across all players.
      - `name` is an optional human-readable display name; without it the class
        name is used. No parentheses (they are reserved for the disambiguation
        suffix the leaderboard adds when two players share a display name).
      - `algo(...)` is called once whenever it is your turn. Return a `Bet` to
        raise the prior bid, or `None` to call "liar" on whoever bid last.

    Bidding rules (see `game/components/bets.py:bet_validator`): a legal raise
    must either increase the quantity, or keep the quantity and increase the
    face. 1s are wild and count toward any non-1 face, unless someone has
    already bid on 1s this round.
    """

    name = "Example"

    def algo(
        self,
        hand: list[int],
        prior_bet: Bet | None,
        total_dice: int,
        bet_history: list[dict],
        outcomes: list[dict],
    ) -> Bet | None:
        """Decide this turn's action.

        Args:
            hand: Your own dice this round, e.g. [3, 3, 6, 1, 2].
            prior_bet: The bet you must beat, or None if you open the round.
            total_dice: How many dice are in play across all players.
            bet_history: Every bet so far this round, oldest first.
            outcomes: Summaries of previous rounds in this game.

        Returns:
            A `Bet` that legally raises `prior_bet`, or `None` to call liar.
        """
        # Tally how many of each face we hold. 1s are wild for non-1 faces, so
        # they reinforce every other face's count.
        counts = {face: hand.count(face) for face in range(1, 7)}
        wilds = counts[1]

        if prior_bet is None:
            # Opening the round: bid the non-1 face we hold the most of (counting
            # wilds), claiming only what we can actually see. An honest opener.
            best_face = max(range(2, 7), key=lambda f: counts[f] + wilds)
            quantity = max(1, counts[best_face] + wilds)
            return Bet(quantity, best_face, self.name)

        # There is a prior bet. If it already claims more than a third of all
        # dice (the break-even point when every 1 is wild), it is probably a
        # bluff - call liar by returning None.
        if prior_bet.quantity > total_dice / 3:
            return None

        # Otherwise make the smallest legal raise: same face, one more die.
        return Bet(prior_bet.quantity + 1, prior_bet.face, self.name)
