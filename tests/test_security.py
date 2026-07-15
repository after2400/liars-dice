"""Tests for the runtime security hardening in game/components/security.py
and game/components/script.py (audit-hook syscall blocking + algo-tampering
detection during game_orchestrator).
"""

import os

import pytest

from game.components.bets import Bet
from game.components.context import GameContext
from game.components.exceptions import SecurityViolation
from game.components.script import game_orchestrator


class Honest:
    name = "Honest"

    def algo(self, ctx: GameContext) -> Bet | None:
        if ctx.prior_bet is None:
            return Bet(1, 2, self.name)
        return None


class Saboteur:
    """Mirrors players/agent_smith.py's frame-hijack monkey-patch technique:
    walk the call stack to grab the orchestrator's `players` local and
    overwrite another player's .algo.
    """

    name = "Saboteur"

    def _victims(self):
        import sys

        frame = sys._getframe(1)
        while frame:
            players = frame.f_locals.get("players")
            if players is not None:
                return players
            frame = frame.f_back
        return None

    def algo(self, ctx: GameContext) -> Bet | None:
        victims = self._victims()
        if victims:
            for p in victims:
                if p is not self:
                    p.algo = lambda ctx: (_ for _ in ()).throw(RuntimeError("pwned"))
        if ctx.prior_bet is None:
            return Bet(1, 2, self.name)
        return None


class SyscallCheater:
    name = "SyscallCheater"

    def algo(self, ctx: GameContext) -> Bet | None:
        os.system("true")  # forbidden shell-out; audit hook should block this
        return Bet(1, 2, self.name)


def test_algo_tampering_raises_security_violation_attributed_to_saboteur():
    """A player that monkey-patches another player's .algo must be caught and
    blamed correctly, regardless of seating order (not the player who acts next)."""
    with pytest.raises(SecurityViolation) as exc_info:
        game_orchestrator([Saboteur(), Honest(), Honest()])
    assert exc_info.value.offender == "Saboteur"


def test_forbidden_syscall_raises_security_violation():
    """A player invoking a forbidden low-level syscall must be blocked by the
    process-wide audit hook installed by secure_environment()."""
    with pytest.raises(SecurityViolation) as exc_info:
        game_orchestrator([SyscallCheater(), Honest()])
    assert exc_info.value.offender == "SyscallCheater"


def test_honest_players_are_unaffected():
    """Sanity check: normal play never trips the security heartbeat."""
    winner = game_orchestrator([Honest(), Honest()], seed=42)
    assert winner is not None


def test_global_random_state_does_not_reveal_dice_rng():
    """The global `random` module (readable by any bot via the whitelisted
    `random` import) must be seeded independently of the private dice RNG, so
    that random.getstate() cannot reconstruct every player's dice.

    Reproducibility for bots that use the global module is preserved: the
    derived seed is still a pure function of the game seed (see the replay
    determinism test in tests/test_replay_engine.py)."""
    import random

    from game.components.script import _derive_player_seed

    game_seed = 0xC0FFEE

    # Derivation is deterministic (replay-safe) ...
    assert _derive_player_seed(game_seed) == _derive_player_seed(game_seed)

    # ... but the global RNG state a bot can observe is NOT the dice RNG state.
    dice_state = random.Random(game_seed).getstate()
    player_state = random.Random(_derive_player_seed(game_seed)).getstate()
    assert player_state != dice_state

    # Concretely: cloning the observable global stream cannot predict the dice.
    random.seed(_derive_player_seed(game_seed))
    clone = random.Random()
    clone.setstate(random.getstate())
    dice_rng = random.Random(game_seed)
    assert clone.choices(range(1, 7), k=10) != dice_rng.choices(range(1, 7), k=10)


class _FakeIsolatedPool:
    """Duck-types just enough of WorkerPool (name_to_index + call) to drive
    game_orchestrator's isolated branch (pool is not None) without spawning
    real subprocess workers.

    `call` also directly tampers with the *other* player's bound `.algo` --
    standing in for whatever cross-process tampering would be impossible in
    a real isolated worker. This only exists to prove the heartbeat loop is
    *skipped*, not merely harmless, once a pool is supplied: if the loop
    still ran here it would see the mismatch and raise SecurityViolation.
    """

    def __init__(self, players):
        self.name_to_index = {p.name: i for i, p in enumerate(players)}
        self._players = players

    def call(self, index, turn):
        prior_bet = turn[1]
        for i, p in enumerate(self._players):
            if i != index:
                p.algo = lambda *a, **k: None
        return Bet(1, 2, None) if prior_bet is None else None


def test_heartbeat_loop_is_skipped_on_isolated_path():
    """Regression for Task 12: with a pool supplied, algo-tampering that
    would trip the in-process heartbeat must NOT raise, because the loop is
    now skipped entirely (not just a no-op) whenever `pool is not None`."""
    a, b = Honest(), Honest()
    a.name, b.name = "A", "B"
    pool = _FakeIsolatedPool([a, b])
    winner = game_orchestrator([a, b], seed=42, pool=pool)
    assert winner is not None


def test_forbidden_syscall_in_init_blocked_at_load(tmp_path, capsys):
    """A bot whose __init__ shells out must be caught when players are loaded,
    not only while algo() runs. The guarded window must cover instantiation —
    the once-per-week construction step where a hostile bot would place exfil.

    Task 15 moved that guarded window out of the parent process entirely: the
    real class is now only ever imported/instantiated inside an isolated
    metadata-probe worker, never in the parent. enforce() still trips on the
    forbidden os.system call, but now it does so INSIDE that worker, which
    crashes before completing its bootstrap handshake — the loader observes
    this the same way it observes any other bootstrap failure (crash, hang,
    missing class): a loud warning and a silent skip of that one player, not
    a SecurityViolation raised out of the loader itself. The syscall is still
    blocked; only how the block is observed by the caller has changed.
    """
    from game.components.utils import import_player_classes_from_dir

    (tmp_path / "shellinit.py").write_text(
        "import os\n"
        "class Shellinit:\n"
        "    def __init__(self):\n"
        "        os.system('true')\n"
        "    def algo(self, ctx):\n"
        "        return None\n"
    )
    players = import_player_classes_from_dir(str(tmp_path))
    assert players == []
    assert "WARNING" in capsys.readouterr().out
