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
