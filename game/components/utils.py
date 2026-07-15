import ast
import inspect
import os
import random as r
from dataclasses import dataclass
from pathlib import Path

from game.components.isolation.pool import WorkerPool
from game.components.isolation.worker import WorkerConfig
from game.components.security import secure_environment

FACES = list(range(1, 7))

# Wall-clock budget for the one-shot metadata-probe worker spawned per player
# file (import + __init__ inside an isolated, scrubbed subprocess). Matches
# game/validate.py's _PROBE_TIMEOUT_S -- this is a roster-load-time cost paid
# once per file, not per game, so the same "how long may one misbehaving bot
# stall us" budget applies.
_PROBE_TIMEOUT_S = 10.0

# Fixed seed for the one-shot metadata probe -- no gameplay ever happens on
# this worker, so determinism doesn't matter.
_PROBE_SEED = b"\x00" * 32


@dataclass
class PlayerSpec:
    """A loaded player plus the source info needed to reload it elsewhere.

    Isolated workers (game/components/isolation/worker.py) reload a player
    BY ABSOLUTE FILE PATH in a fresh interpreter, not by module name —
    `spec_from_file_location`'s module name is a bare stem, not importable
    after a `multiprocessing.get_context("spawn")` re-exec. `abs_file_path`
    exists so `run_series`'s isolated path (game/components/series.py) can
    build a `WorkerConfig` for each player without re-deriving that path.
    """

    player_obj: object
    abs_file_path: str
    class_name: str


def _parse_player_class(source: str, stem: str) -> tuple[str, list[str]] | None:
    """Pure syntax parse (no execution): returns (class_name, algo_arg_names)
    for the top-level class in `source` whose name matches `stem`
    case-insensitively, or None if no such class (or no `algo` method on it)
    exists. `algo_arg_names` includes "self".

    Deliberately duplicated from game/validate.py's `_find_class_and_algo_args`
    (same ~15 lines) rather than imported: validate.py is a CLI-level gate
    built on top of game.components.isolation, while this module is a lower
    layer that validate.py's own imports never reach back into — importing
    "up" from a components module into the top-level validate tool would
    invert that dependency direction for the sake of a very small helper.
    Both copies should be kept in sync by hand if the class/algo shape ever
    changes; see the report for the full reasoning on this call.
    """
    tree = ast.parse(source)
    class_node = next(
        (n for n in tree.body if isinstance(n, ast.ClassDef) and n.name.lower() == stem.lower()),
        None,
    )
    if class_node is None:
        return None
    algo_node = next(
        (n for n in class_node.body if isinstance(n, ast.FunctionDef) and n.name == "algo"),
        None,
    )
    if algo_node is None:
        return None
    return class_node.name, [a.arg for a in algo_node.args.args]


def _make_stub_algo(arg_names: list[str]):
    """Build a stub `algo` function whose `inspect.signature` matches the real
    bot's declared shape (from `_parse_player_class`'s AST-derived
    `arg_names`, "self" included) without ever running the real player's code.

    `game/components/script.py`'s `game_orchestrator` unconditionally computes
    `inspect.signature(p.algo).parameters` for every player at game start to
    decide v1/v2 dispatch — this runs regardless of isolation, so a shell
    player object with no usable `.algo` would crash every real game
    immediately. The stub's actual body is never meant to run in the parent;
    real games only ever call the real algo() inside the isolated worker
    (game/components/isolation/worker.py), keyed off `_isolation_spec`.
    """

    def _stub(self, *args, **kwargs):
        raise NotImplementedError(
            "shell player object — real algo() only runs inside the isolated worker"
        )

    _stub.__signature__ = inspect.Signature(
        [inspect.Parameter(a, inspect.Parameter.POSITIONAL_OR_KEYWORD) for a in arg_names]
    )
    return _stub


def _probe_player_metadata(abs_file_path: str, class_name: str) -> tuple | None:
    """One-shot isolated bootstrap probe for name/avatar metadata.

    Spawns a real worker (scrubbed env, restricted cwd, enforce()'d import +
    instantiation — see worker_main) and returns its bootstrap handshake
    payload, `("ready", name, avatar)`, without ever issuing a turn:
    `_Worker.__init__` -> `_spawn()` captures `ready_info` during
    construction itself (`self.ready_info = self.parent_conn.recv()`),
    *before* any `.call()`, so roster loading — unlike game/validate.py's
    `_runtime_errors`, which also probes one algo() turn to verify it
    doesn't crash — needs no probe turn at all.

    Returns None if the worker never completes its bootstrap handshake
    (crash or hang during import/instantiation) — mirrors validate.py's
    WORKER_ERROR case.
    """
    cfg = WorkerConfig(
        player_file=abs_file_path,
        player_class=class_name,
        name=class_name,  # placeholder; apply_display_names overwrites .name later anyway
        global_random_seed=_PROBE_SEED,
    )
    with WorkerPool([cfg], timeout_s=_PROBE_TIMEOUT_S) as pool:
        return pool.workers[0].ready_info


def import_player_specs_from_dir(directory) -> list["PlayerSpec"]:
    # Roster loading must never run a real player's module-level code or
    # __init__ in THIS (parent) process — that would be the once-per-run
    # window where a hostile bot's untrusted constructor runs with the real
    # (unscrubbed) environment still in os.environ, fully able to read
    # GH_TOKEN/LEADERBOARD_PAT before any worker isolation ever kicks in.
    # Same-process scrub-then-restore was considered and rejected: enforce()'s
    # audit hook doesn't block thread creation, so a malicious __init__ could
    # spawn a background thread that simply waits past the restore point and
    # reads the secret later.
    #
    # Instead: get the class name + algo() arg shape via pure AST parsing (no
    # execution), get name/avatar via a one-shot isolated worker probe (real
    # import + __init__, but inside worker_main's scrubbed subprocess), and
    # build a lightweight synthetic "shell" instance here in the parent that
    # satisfies every real caller's actual usage (type(p).__name__ for
    # tier/roster filtering, .name for display, and a stub .algo whose
    # inspect.signature matches the real declared shape). The real class is
    # never imported and never instantiated in this process.
    secure_environment()
    specs: list[PlayerSpec] = []
    for filename in os.listdir(directory):
        if not filename.endswith(".py"):
            continue
        stem = filename[:-3]
        module_path = os.path.join(directory, filename)
        abs_file_path = os.path.abspath(module_path)
        source = Path(module_path).read_text()

        parsed = _parse_player_class(source, stem)
        if parsed is None:
            # No class matching the filename stem (case-insensitive) with an
            # algo method — preserves the old loader's silent skip for
            # in-development or intentionally-invalid files (e.g. the
            # untracked players/the_architect.py fixture).
            continue
        class_name, algo_arg_names = parsed

        ready_info = _probe_player_metadata(abs_file_path, class_name)
        if ready_info is None:
            # This is a previously-registered, previously-passing bot
            # suddenly failing to even bootstrap (crash or hang during
            # import/__init__ inside the isolated probe worker). Don't crash
            # the whole season/roster load over one bad bot, but make the
            # skip loud — unlike the "file doesn't match naming convention"
            # skip above, this is a genuine anomaly worth a human's attention.
            print(
                f"[WARNING] {stem}: isolated bootstrap probe failed (crash or "
                f"hang during import/instantiation) — skipping this player "
                f"for this run"
            )
            continue

        shell_cls = type(class_name, (), {"algo": _make_stub_algo(algo_arg_names)})
        player_obj = shell_cls()
        live_name = ready_info[1]
        player_obj.name = live_name if live_name is not None else class_name

        player_spec = PlayerSpec(
            player_obj=player_obj,
            abs_file_path=abs_file_path,
            class_name=class_name,
        )
        # Tag the instance with its own spec so callers that only ever go
        # through import_player_classes_from_dir (every current call site —
        # season.py/tournament.py/quarter.py/__main__.py — none of which are
        # changed in this task) still let it travel invisibly to wherever a
        # player object ends up, e.g. run_series's isolated path, which needs
        # the source file + class name to build a WorkerConfig. Private
        # attribute, not part of the player interface.
        player_obj._isolation_spec = player_spec
        specs.append(player_spec)
    return specs


def import_player_classes_from_dir(directory):
    """Thin wrapper over import_player_specs_from_dir for callers that only need
    the instantiated player objects. See PlayerSpec / import_player_specs_from_dir
    for the full load (also tags each returned object with `._isolation_spec`)."""
    return [s.player_obj for s in import_player_specs_from_dir(directory)]


def apply_display_names(players: list, lb_players: dict) -> None:
    """Set player.name to the deduplicated display name from the leaderboard.

    When two players share the same display_name, build_display_names appends
    a (github_username) suffix so each in-game name is unique. Players not
    registered in lb_players are left untouched.
    """
    from game.components.leaderboard import build_display_names

    display_names = build_display_names(lb_players)
    for p in players:
        class_name = type(p).__name__
        if class_name in display_names:
            p.name = display_names[class_name]


def roll_dice(hands: list):
    for h in hands:
        h["hand"] = r.choices(FACES, k=h["n_dice"])
    return hands
