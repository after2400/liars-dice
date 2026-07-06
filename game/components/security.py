import contextlib
import logging
import sys
from typing import Set

from game.components.exceptions import SecurityViolation

logger = logging.getLogger(__name__)

# The audit hook, once installed, is process-global and permanent — that's
# the point (a malicious bot can't remove it). But that also means it would
# otherwise fire for perfectly legitimate subprocess/socket use elsewhere in
# the *same process* (e.g. validate_player.py's sandboxing, or any other test
# in a shared pytest session) long after a game has finished. _enforcing
# scopes actual blocking to the window where a player's algo() is on the
# stack, so the hook only ever penalizes player code.
_enforcing = False


@contextlib.contextmanager
def enforce():
    """Marks the enclosed block as player-controlled code subject to the
    forbidden-syscall audit hook."""
    global _enforcing
    previous = _enforcing
    _enforcing = True
    try:
        yield
    finally:
        _enforcing = previous


class SecurityManager:
    """Handles runtime hardening via a process-wide audit hook."""

    # Every entry here must correspond to a real CPython audit event (see
    # sys.audit / PEP 578). "os.write", "os.setuid", "os.setgid" and
    # "socket.create_connection" are *not* real audit events and never fire —
    # verified empirically; don't add entries back without checking they
    # actually trigger via sys.addaudithook.
    FORBIDDEN_EVENTS: Set[str] = {
        "os.system",
        "subprocess.Popen",
        "socket.connect",
        "socket.sendto",
    }

    @staticmethod
    def _audit_handler(event: str, args: tuple):
        if _enforcing and event in SecurityManager.FORBIDDEN_EVENTS:
            raise SecurityViolation(f"Forbidden syscall {event} detected")

    @classmethod
    def install_audit_hooks(cls):
        """Installs the system audit hook to monitor forbidden events."""
        try:
            sys.addaudithook(cls._audit_handler)
            logger.info("Security audit hooks installed successfully.")
        except Exception as e:
            logger.error(f"Failed to install audit hooks: {e}")


def secure_environment():
    """Initializes the security fortress."""
    SecurityManager.install_audit_hooks()
