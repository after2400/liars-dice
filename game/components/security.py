import logging
import sys
from typing import Set

logger = logging.getLogger(__name__)


class SecurityManager:
    """Handles runtime hardening, including audit hooks and module protection."""

    FORBIDDEN_EVENTS: Set[str] = {
        "os.write",
        "os.setuid",
        "os.setgid",
        "socket.connect",
        "socket.sendto",
        "socket.create_connection",
    }

    @staticmethod
    def _audit_handler(event: str, args: tuple):
        if event in SecurityManager.FORBIDDEN_EVENTS:
            # We don't raise here because we want the orchestrator to handle
            # the exception flow if it's wrapped, but audit hooks are global.
            # Raising a RuntimeError inside an audit hook is the standard way to block.
            raise RuntimeError(f"Security Violation: Forbidden syscall {event} detected")

    @classmethod
    def install_audit_hooks(cls):
        """Installs the system audit hook to monitor forbidden events."""
        try:
            sys.addaudithook(cls._audit_handler)
            logger.info("Security audit hooks installed successfully.")
        except Exception as e:
            logger.error(f"Failed to install audit hooks: {e}")

    @staticmethod
    def freeze_module(module):
        """
        Attempts to prevent modification of a module's attributes.
        Note: This is limited for built-in modules but works for local packages.
        """
        try:
            # For custom modules, we can try to wrap the module in a proxy or
            # just log attempts if they are modified (which the Heartbeat already does).
            # Here we'll implement a simple attribute lock if possible.
            if hasattr(module, "__setattr__"):

                def locked_setattr(name, value):
                    raise RuntimeError(
                        f"Security Violation: Modification of frozen module {module.__name__} forbidden"
                    )

                module.__setattr__ = locked_setattr
        except Exception as e:
            logger.debug(f"Could not freeze module {getattr(module, '__name__', 'unknown')}: {e}")


def secure_environment(*modules):
    """Initializes the security fortress."""
    SecurityManager.install_audit_hooks()
    for mod in modules:
        SecurityManager.freeze_module(mod)
