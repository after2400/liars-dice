"""Child-side entry point for an isolated player worker.

Bootstrap order is security-critical: scrub secrets from env BEFORE importing any
untrusted player code, restrict the cwd, install the syscall audit hooks, then
import + instantiate the player under enforce().
"""

import importlib.util
import os
import random
import tempfile
from dataclasses import dataclass

from game.components.isolation import protocol
from game.components.isolation.env import scrub_environment


@dataclass
class WorkerConfig:
    player_file: str  # absolute path to the player's .py (NOT a module name)
    player_class: str
    name: str  # final display name to reassign (parent sets this post-load)
    global_random_seed: bytes
    # shared_memory block name for the read-only bet-history/outcomes read-model
    # (game/components/isolation/readmodel.py). None means no read-model is
    # available and the worker falls back to empty history/outcomes — keeps
    # existing positional WorkerConfig(...) call sites (tests, older callers)
    # working without every one of them needing an update for this task.
    readmodel_name: str | None = None


def _build_args(player, turn, is_v2, reader=None, wants_stats=False):
    from game.components.bets import Bet

    hand, prior_bet, total_dice, tier, round_players, log_len = turn
    pb = Bet(prior_bet[0], prior_bet[1], prior_bet[2]) if prior_bet is not None else None
    if is_v2:
        from game.components.context import GameContext, _ReadOnlySequence

        if reader is not None:
            bet_history = reader.bet_history_view(log_len)
            outcomes = reader.outcomes_view()
            stats = reader.stats_view()
        else:
            bet_history = _ReadOnlySequence([])
            outcomes = _ReadOnlySequence([])
            stats = None

        return (
            GameContext(
                hand=list(hand),
                prior_bet=pb,
                total_dice=total_dice,
                bet_history=bet_history,
                outcomes=outcomes,
                stats=stats,
                tier=tier,
                round_players=list(round_players),
            ),
        ), {}

    kwargs: dict = {}
    if wants_stats:
        kwargs["stats"] = reader.stats_view() if reader is not None else None
    return (list(hand), pb, total_dice, [], []), kwargs


def worker_main(conn, cfg: WorkerConfig):
    # 1. Scrub secrets from our inherited environment FIRST.
    scrub_environment(os.environ)
    # 2. Restrict cwd to an ephemeral private dir (no write access to the checkout).
    workdir = tempfile.mkdtemp(prefix="ld-worker-")
    os.chdir(workdir)
    # 3. Seed this worker's global random (independent, deterministic per player).
    random.seed(cfg.global_random_seed)
    # 4. Install audit hooks, then load the player BY FILE PATH (mirrors
    #    import_player_classes_from_dir — module name is not importable in a fresh
    #    interpreter; players/ is not a package), instantiate, reassign name.
    from game.components.security import enforce, secure_environment

    secure_environment()
    with enforce():
        stem = os.path.basename(cfg.player_file)[:-3]
        spec = importlib.util.spec_from_file_location(stem, cfg.player_file)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        player = getattr(module, cfg.player_class)()
    player.name = cfg.name

    import inspect

    sig = inspect.signature(player.algo).parameters
    positional = sum(
        1
        for nm, prm in sig.items()
        if nm != "self" and prm.kind in (prm.POSITIONAL_ONLY, prm.POSITIONAL_OR_KEYWORD)
    )
    is_v2 = positional == 1
    # v2 bots always receive stats via GameContext.stats; v1 bots only if they
    # opted in by naming a `stats` parameter (mirrors script.py's _wants_stats).
    wants_stats = is_v2 or "stats" in sig

    # Open the read-model once, before the turn loop (not per-turn): mapping is a
    # one-time O(1) setup cost; each turn thereafter only does direct offset reads.
    reader = None
    if cfg.readmodel_name is not None:
        from game.components.isolation.readmodel import ReadModelReader

        reader = ReadModelReader(cfg.readmodel_name)

    conn.send("ready")
    while True:
        turn = conn.recv()
        if turn is None:
            break
        try:
            with enforce():
                args, kwargs = _build_args(player, turn, is_v2, reader, wants_stats)
                action = player.algo(*args, **kwargs)
            conn.send_bytes(protocol.encode_result(action))
        except Exception:
            conn.send_bytes(protocol.encode_result(protocol.WORKER_ERROR))
