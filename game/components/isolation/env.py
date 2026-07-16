"""Remove CI secrets from a worker's inherited environment.

Environment variables are inherited across `spawn`, so a worker would otherwise
see GH_TOKEN / LEADERBOARD_PAT. Scrubbing them is the first action a worker takes,
before any untrusted code runs — without it, process isolation is defeated by the
child's own environment.
"""

from collections.abc import MutableMapping

_DENYLIST = frozenset(
    {
        "GH_TOKEN",
        "LEADERBOARD_PAT",
        "GITHUB_TOKEN",
        "ACTIONS_RUNTIME_TOKEN",
        "ACTIONS_ID_TOKEN_REQUEST_TOKEN",
    }
)
_SUFFIXES = ("_TOKEN", "_PAT", "_KEY", "_SECRET", "_PASSWORD")


def scrub_environment(environ: MutableMapping[str, str]) -> list[str]:
    """Delete secret-looking names from `environ` in place; return removed names sorted."""
    to_remove = [name for name in environ if name in _DENYLIST or name.upper().endswith(_SUFFIXES)]
    for name in to_remove:
        del environ[name]
    return sorted(to_remove)
