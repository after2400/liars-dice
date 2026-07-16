"""Task 15 regression tests: import_player_specs_from_dir must never run a
real player's module-level code or __init__ in the parent process.

Before this task, the loader did `spec.loader.exec_module(module)` and
`player_class()` directly in-process, guarded only by enforce()'s syscall
audit hook -- never by env scrubbing. That meant a bot's untrusted __init__
had a window, on every real season/tournament/quarter run, where the real
GH_TOKEN/LEADERBOARD_PAT were still in os.environ. The fix: get the class
name via pure AST parsing (no execution), get name/avatar via a one-shot
isolated worker probe (the real class only ever runs inside a scrubbed
subprocess), and return a lightweight synthetic "shell" instance to the
parent -- the real class is never imported and never instantiated here.
"""

import inspect
from pathlib import Path

from game.components.series import run_series
from game.components.utils import apply_display_names, import_player_specs_from_dir

REPO_ROOT = Path(__file__).parent.parent

_LEAKY_BOT_SRC = '''
import os


class LeakyBot:
    """If instantiated unscrubbed in the parent, this would capture the real
    secret straight out of os.environ."""

    def __init__(self):
        self.leaked = os.environ.get("GH_TOKEN")

    def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):
        return None
'''


def test_leaked_secret_never_reaches_parent_shell(tmp_path, monkeypatch):
    """The actual regression test for the security bug: a real-looking
    secret in the parent's os.environ must never end up captured on the
    object returned by the loader, even though the bot's __init__ explicitly
    tries to read it.
    """
    monkeypatch.setenv("GH_TOKEN", "definitely-a-real-looking-secret-value")
    (tmp_path / "leakybot.py").write_text(_LEAKY_BOT_SRC)

    specs = import_player_specs_from_dir(str(tmp_path))
    assert len(specs) == 1
    player_obj = specs[0].player_obj

    # Proves the real __init__ never ran in this process at all -- the shell
    # object is a distinct, empty class, so it has no `leaked` attribute
    # regardless of what the real (scrubbed, isolated-worker) __init__ saw.
    assert not hasattr(player_obj, "leaked")


def test_shell_class_name_matches_real_but_is_not_the_real_class(tmp_path):
    (tmp_path / "leakybot.py").write_text(_LEAKY_BOT_SRC)

    specs = import_player_specs_from_dir(str(tmp_path))
    player_obj = specs[0].player_obj

    # String identity holds for every type(p).__name__-keyed lookup across
    # the real callers (season.py/tournament.py/__main__.py/tui)...
    assert type(player_obj).__name__ == "LeakyBot"

    # ...but the type itself is a synthetic shell, not the real imported class.
    import importlib.util

    spec = importlib.util.spec_from_file_location("leakybot", str(tmp_path / "leakybot.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    RealLeakyBot = module.LeakyBot

    assert type(player_obj) is not RealLeakyBot
    assert not isinstance(player_obj, RealLeakyBot)


def test_shell_name_defaults_to_class_name_and_apply_display_names_works(tmp_path):
    # LeakyBot declares no `name` attribute and the worker reports no
    # dynamically-set name, so the shell must fall back to the class name --
    # mirrors validate.py's exact fallback.
    (tmp_path / "leakybot.py").write_text(_LEAKY_BOT_SRC)

    specs = import_player_specs_from_dir(str(tmp_path))
    player_obj = specs[0].player_obj
    assert player_obj.name == "LeakyBot"

    # apply_display_names only ever does p.name = display_names[class_name] --
    # should work identically on a shell object.
    lb_players = {"LeakyBot": {"display_name": "Leaky", "github_username": "someone"}}
    apply_display_names([player_obj], lb_players)
    assert player_obj.name == "Leaky"


def test_shell_algo_signature_matches_real_v2_bot():
    # players/deepthought.py: def algo(self, ctx) -- v2 interface.
    specs = import_player_specs_from_dir(str(REPO_ROOT / "players"))
    dt_spec = next(s for s in specs if s.class_name == "DeepThought")
    params = inspect.signature(dt_spec.player_obj.algo).parameters
    assert list(params) == ["ctx"]


def test_worker_bootstrap_crash_is_skipped_not_raised(tmp_path, capsys):
    """A player file whose class exists (AST match succeeds) but whose
    module crashes at import time inside the isolated probe worker must be
    skipped loudly, not raise out of the loader and take down the whole
    roster load."""
    # Filename stem must match the class name case-insensitively (the
    # loader's naming convention) for _parse_player_class to find a match at
    # all -- "crashesatimport.py" (no underscores), not the examples/
    # fixture's original "crashes_at_import.py" name.
    crash_src = (REPO_ROOT / "examples" / "crashes_at_import.py").read_text()
    (tmp_path / "crashesatimport.py").write_text(crash_src)

    specs = import_player_specs_from_dir(str(tmp_path))

    assert specs == []
    captured = capsys.readouterr()
    assert "crashesatimport" in captured.out
    assert "WARNING" in captured.out


def test_isolated_series_runs_end_to_end_with_loader_players(tmp_path):
    """Parity/regression check: players loaded via import_player_specs_from_dir
    (shell objects, no real class ever constructed in-parent) must still work
    as the isolated=True path's input -- the shell's `_isolation_spec` is all
    `run_series` needs to reload the real class inside each worker.
    """
    for name in ("rick.py", "deepthought.py"):
        (tmp_path / name).write_text((REPO_ROOT / "players" / name).read_text())

    players = [s.player_obj for s in import_player_specs_from_dir(str(tmp_path))]
    assert len(players) == 2
    for p in players:
        p.name = type(p).__name__

    result = run_series(players, n_games=2, isolated=True, worker_timeout_s=10.0)

    assert sum(result.wins.values()) == 2
