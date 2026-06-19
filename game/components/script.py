import inspect
import logging
import random
import secrets
import traceback
import types

from game.components.bets import Bet, bet_grader, bet_validator
from game.components.context import GameContext, _ReadOnlySequence
from game.components.utils import FACES

logger = logging.getLogger(__name__)


def game_orchestrator(
    players: list,
    game_id: int = 1,
    bet_history: list[dict] | None = None,
    outcomes: list[dict] | None = None,
    stats=None,
    tier: str | None = None,
):
    """Plays a complete game of Liar's Dice between N players.

    Each round, all active players roll their dice in secret. Players take
    turns bidding (quantity, face). A player may call liar instead of bidding,
    triggering a reveal. The loser of each challenge loses one die; a player
    eliminated when they reach 0 dice. Last player standing wins.

    Args:
        players: List of player objects. Each must implement
                 algo(hand, prior_bet, total_dice, bet_history, outcomes) -> Bet | None.
        game_id: Identifier for this game, stored on every bet_history and outcomes entry.
        bet_history: Shared list to append bids to. Created fresh if not provided.
        outcomes: Shared list to append round outcomes to. Created fresh if not provided.

    Returns:
        The winning player object.
    """
    rng = random.Random(secrets.randbits(64))
    _sigs = {p: inspect.signature(p.algo).parameters for p in players}
    _wants_stats = {p: "stats" in _sigs[p] for p in players}
    _wants_tier = {p: "tier" in _sigs[p] for p in players}
    _wants_round_players = {p: "round_players" in _sigs[p] for p in players}

    def _positional_count(params: dict) -> int:
        return sum(
            1
            for name, p in params.items()
            if name != "self"
            and p.kind
            in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
            )
        )

    _is_v2 = {p: _positional_count(_sigs[p]) == 1 for p in players}
    logger.info("=== New Game ===")
    rng.shuffle(players)
    logger.info(f"Players: {', '.join(p.name for p in players)}")

    n = len(players)
    dice_counts = [5] * n
    eliminated = [False] * n

    def active():
        return [i for i in range(n) if not eliminated[i]]

    first_player = rng.choice(active())
    logger.info(f"First to bet: {players[first_player].name}")

    if bet_history is None:
        bet_history = []
    if outcomes is None:
        outcomes = []
    completed_outcomes = outcomes  # alias — appended to in-place below

    # Read-only wrappers created once per game, shared across all v2 player turns.
    bet_history_view = _ReadOnlySequence(bet_history)
    outcomes_view = _ReadOnlySequence(completed_outcomes)

    round_num = 0

    while len(active()) > 1:
        round_num += 1
        active_list = active()
        dice_summary = "  ".join(f"{players[i].name}:{dice_counts[i]}" for i in active_list)
        logger.info("")
        logger.info(f"--- Round {round_num}  |  {dice_summary} ---")

        # Roll dice for all active players
        hands = {i: rng.choices(FACES, k=dice_counts[i]) for i in active_list}
        for i in active_list:
            logger.debug(f"  {players[i].name} rolled: {hands[i]}")

        total_dice = sum(dice_counts[i] for i in active_list)
        start_pos = active_list.index(first_player)
        round_players_order = [
            players[active_list[(start_pos + i) % len(active_list)]].name
            for i in range(len(active_list))
        ]
        step = 0
        current_bet: Bet | None = None
        prev_bidder: int | None = None
        loser: int | None = None
        round_winner: int | None = None  # winner of the liar challenge; leads next round
        wilds = True  # flips to False once someone bids on 1s
        ones_allowed = None  # set after first bid: True if opened on 1s, False otherwise

        while loser is None:
            player_idx = active_list[(start_pos + step) % len(active_list)]
            player = players[player_idx]

            try:
                safe_bet = (
                    Bet(current_bet.quantity, current_bet.face, current_bet.player)
                    if current_bet is not None
                    else None
                )
                if _is_v2[player]:
                    ctx = GameContext(
                        hand=list(hands[player_idx]),
                        prior_bet=safe_bet,
                        total_dice=total_dice,
                        bet_history=bet_history_view,
                        outcomes=outcomes_view,
                        stats=stats,
                        tier=tier,
                        round_players=round_players_order,
                    )
                    action = player.algo(ctx)
                else:
                    kwargs: dict = {}
                    if _wants_stats[player]:
                        kwargs["stats"] = stats
                    if _wants_tier[player]:
                        kwargs["tier"] = tier
                    if _wants_round_players[player]:
                        kwargs["round_players"] = list(round_players_order)
                    action = player.algo(
                        list(hands[player_idx]),
                        safe_bet,
                        total_dice,
                        list(bet_history),
                        list(completed_outcomes),
                        **kwargs,
                    )
            except Exception:
                logger.error(
                    "%s raised an exception - penalised\n%s",
                    player.name,
                    traceback.format_exc().rstrip(),
                )
                loser = player_idx
                break

            if action is None:
                # Player calls liar
                if current_bet is None:
                    logger.warning(f"{player.name} called liar with no prior bet - penalised")
                    loser = player_idx
                else:
                    logger.info(
                        f"{player.name} calls LIAR on [{current_bet}] "
                        f"(bet by {players[prev_bidder].name})"
                    )
                    all_hands = list(hands.values())
                    logger.debug(f"  All dice: {all_hands}")
                    bet_held = bet_grader(all_hands, current_bet, wilds)
                    if bet_held:
                        logger.info(f"Bet holds - {player.name} loses a die")
                        loser = player_idx
                        round_winner = prev_bidder
                    else:
                        logger.info(f"Bet fails - {players[prev_bidder].name} loses a die")
                        loser = prev_bidder
                        round_winner = player_idx
                    completed_outcomes.append(
                        types.MappingProxyType(
                            {
                                "game": game_id,
                                "round": round_num,
                                "hands": types.MappingProxyType(
                                    {players[i].name: tuple(hands[i]) for i in active_list}
                                ),
                                "final_bet": current_bet,
                                "bidder": players[prev_bidder].name,
                                "challenger": player.name,
                                "bet_held": bet_held,
                                "loser": players[loser].name,
                            }
                        )
                    )
                    if stats is not None:
                        stats.update_outcome(completed_outcomes[-1])
                        stats.reset_round(round_num + 1)
            else:
                # Player makes a new bid
                if ones_allowed is False and action.face == 1:
                    logger.warning(f"{player.name} bid on 1s after non-1 opening bid - penalised")
                    loser = player_idx
                elif current_bet is not None and not bet_validator(current_bet, action):
                    logger.warning(f"{player.name} made invalid bid [{action}] - penalised")
                    loser = player_idx
                else:
                    if ones_allowed is None:
                        ones_allowed = action.face == 1
                    current_bet = action
                    prev_bidder = player_idx
                    bet_history.append(
                        types.MappingProxyType(
                            {
                                "game": game_id,
                                "round": round_num,
                                "player": player.name,
                                "bet": current_bet,
                                "dice_count": dice_counts[player_idx],
                            }
                        )
                    )
                    if stats is not None:
                        stats.update_bet(
                            bet_history[-1],
                            is_opening_bid=(step == 0),
                            total_dice=total_dice,
                        )
                    if current_bet.face == 1 and wilds:
                        wilds = False
                        logger.info(
                            f"  {player.name} bets: [{current_bet}]  (1s are no longer wild)"
                        )
                    else:
                        logger.info(f"  {player.name} bets: [{current_bet}]")
                    step += 1

        # Apply the loss
        dice_counts[loser] -= 1
        if dice_counts[loser] == 0:
            eliminated[loser] = True
            logger.info(f"{players[loser].name} loses their last die - ELIMINATED")
        else:
            logger.info(f"{players[loser].name} loses a die - now has {dice_counts[loser]}")

        # Winner of the challenge leads next round; penalty cases fall back to next clockwise
        if round_winner is not None:
            first_player = round_winner
        else:
            loser_pos = active_list.index(loser)
            first_player = active_list[(loser_pos + 1) % len(active_list)]

    winner = players[active()[0]]
    logger.info("")
    logger.info(f"=== {winner.name} WINS! ===")
    return winner
