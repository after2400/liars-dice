"""Validate a player file via AST analysis then limited runtime checks.

Two-phase approach:
  Phase 1 (no code execution): import whitelist, absence of module-level
  executable statements, class structure, algo signature, display name.
  Phase 2 (runtime, only if Phase 1 passes): instantiation and tier=None
  probe — safe because Phase 1 already enforced the import whitelist.

Usage:
    uv run python -m game.validate players/fred.py

Exits 0 on success, 1 on any failure.
"""

import ast
import re
import sys
from pathlib import Path

from game.components.isolation import protocol
from game.components.isolation.pool import WorkerPool
from game.components.isolation.worker import WorkerConfig

# Wall-clock budget for the isolated instantiate-and-probe worker. Replaces
# the old in-process SIGALRM-based _INSTANTIATION_TIMEOUT (10s) -- same
# magnitude, but enforced by WorkerPool's real process kill() rather than a
# signal handler, which can't interrupt a blocking native/C-level call.
_PROBE_TIMEOUT_S = 10.0

# Empty-history probe turn: (hand, prior_bet, total_dice, tier, round_players,
# log_len). Matches worker.py's _build_args turn-tuple shape. No shared
# read-model is wired up -- worker.py already falls back to empty
# bet_history/outcomes when WorkerConfig.readmodel_name is None.
_PROBE_TURN = ([], None, 10, None, [], 0)

# Fixed seed for the one-shot probe worker -- determinism doesn't matter here.
_PROBE_SEED = b"\x00" * 32

MAX_NAME_LEN = 25


# --- display-name rules (imported by registration and rename scripts) ---


def validate_display_name(name: str) -> str | None:
    """Return an error message if `name` is an invalid display name, else None.

    The single source of truth for the display-name rules. Imported by the
    registration and rename scripts so the length limit and the parenthesis
    rule can never drift apart across the three places that enforce them.
    """
    if len(name) > MAX_NAME_LEN:
        return f"name '{name}' exceeds {MAX_NAME_LEN} characters"
    if "(" in name or ")" in name:
        return "name may not contain parentheses (reserved for username suffix)"
    return None


# --- avatar rules (imported by registration and rename scripts) ---

_CLOUD_NAME_RE = re.compile(r"^[a-z0-9-]+\Z")
_PUBLIC_ID_EXT_RE = re.compile(r"^[A-Za-z0-9_./-]+\Z")
_AVATAR_EXTENSIONS = frozenset({"png", "jpg", "jpeg", "gif", "webp"})


def validate_avatar(value: str) -> str | None:
    """Return an error message if `value` is not a valid avatar identifier, else None.

    Expects "cloud_name/public_id.ext" — the substring of a Cloudinary
    delivery URL that comes after ".../image/upload/". This is the single
    source of truth, imported by registration and sync scripts. The host
    (`res.cloudinary.com`) is always a literal in the code that renders this
    value, never derived from it, so no value that passes here can ever
    redirect an <img> tag off Cloudinary's domain.
    """
    if not isinstance(value, str) or "/" not in value:
        return f"avatar '{value}' must be in the form 'cloud_name/public_id.ext'"
    cloud_name, public_id_ext = value.split("/", 1)
    if not _CLOUD_NAME_RE.match(cloud_name):
        return (
            f"avatar cloud_name '{cloud_name}' is not valid "
            "(lowercase letters, digits, and hyphens only)"
        )
    if ".." in public_id_ext:
        return f"avatar public_id '{public_id_ext}' may not contain '..'"
    if not _PUBLIC_ID_EXT_RE.match(public_id_ext):
        return (
            f"avatar public_id '{public_id_ext}' is not valid "
            "(letters, digits, '_', '-', '.', '/' only)"
        )
    ext = public_id_ext.rsplit(".", 1)[-1] if "." in public_id_ext else ""
    if ext not in _AVATAR_EXTENSIONS:
        return f"avatar '{value}' must end with one of: {', '.join(sorted(_AVATAR_EXTENSIONS))}"
    return None


# --- import whitelist ---

# Allowed top-level stdlib packages. No network, no filesystem, no introspection.
_ALLOWED_STDLIB: frozenset[str] = frozenset(
    {
        "__future__",
        "abc",
        "collections",
        "copy",
        "dataclasses",
        "enum",
        "functools",
        "itertools",
        "logging",
        "math",
        "operator",
        "random",
        "types",
        "typing",
    }
)

# game.* submodules players are allowed to import explicitly.
_ALLOWED_GAME_MODULES: frozenset[str] = frozenset(
    {
        "game.components.bets",
        "game.components.context",
        "game.components.stats",
    }
)


def _import_allowed(module: str) -> bool:
    if module.startswith("game"):
        return module in _ALLOWED_GAME_MODULES
    if module.split(".")[0] not in _ALLOWED_STDLIB:
        return False
    # Only top-level stdlib modules are importable. Dotted submodules can expose
    # capabilities the top-level package doesn't (e.g. logging.handlers brings
    # SocketHandler/HTTPHandler — outbound network); no whitelisted module needs
    # one, so the whole dotted form is refused rather than enumerated.
    return "." not in module


# --- AST phase ---

# Module-level node types that require no execution.
# Assignments are allowed because the import whitelist prevents dangerous symbols
# from being available (e.g. `logger = logging.getLogger(__name__)` is fine).
_SAFE_TOPLEVEL = (
    ast.Import,
    ast.ImportFrom,
    ast.ClassDef,
    ast.FunctionDef,
    ast.AsyncFunctionDef,
    ast.Assign,
    ast.AnnAssign,
    ast.AugAssign,
)

# Builtins that allow arbitrary code execution or unsafe I/O — blocked everywhere
# in the file so they can't be called inside algo() either.
_BLOCKED_BUILTINS: frozenset[str] = frozenset({"exec", "eval", "__import__", "compile", "open"})

# Attribute names that expose interpreter internals — blocked anywhere in the
# file (as attribute access or as a call). Two escape classes:
#   1. Call-frame / traceback / generator introspection: reaching the running
#      orchestrator's frame lets a bot read `hands` (every player's dice). This
#      needs no import — an exception's __traceback__ or a generator's gi_frame
#      is enough — so the import whitelist cannot stop it; the attribute names
#      must be. (See The Architect.)
#   2. Pivots into a dangerous module re-exported by an allowed one: whitelisting
#      `logging` otherwise hands a bot `logging.os` (env/secret read),
#      `logging.sys`, `logging.socket`, etc.
_BLOCKED_ATTRS: frozenset[str] = frozenset(
    {
        # frame / traceback / generator-coroutine frame introspection
        "f_back",
        "f_locals",
        "f_globals",
        "f_code",
        "f_builtins",
        "gi_frame",
        "cr_frame",
        "ag_frame",
        "tb_frame",
        "tb_next",
        "__traceback__",
        "_getframe",
        # function / class internals that reach module globals or code objects
        "__globals__",
        "__code__",
        "__closure__",
        # pivots into re-exported dangerous stdlib modules (e.g. logging.os)
        "os",
        "sys",
        "subprocess",
        "socket",
        "importlib",
        "builtins",
        "traceback",
        "ctypes",
        "marshal",
        "runpy",
        "pty",
    }
)

_V2_ALGO_ARGS = ("self", "ctx")

_CLASS_STR_ATTR_VALIDATORS = {
    "name": validate_display_name,
    "avatar": validate_avatar,
}


def _check_str_literal(attr_name: str, value_node: ast.expr, errors: list[str]) -> None:
    """Validate a class-level attribute's AST value is a string literal passing its rule."""
    validator = _CLASS_STR_ATTR_VALIDATORS[attr_name]
    if isinstance(value_node, ast.Constant) and isinstance(value_node.value, str):
        err = validator(value_node.value)
        if err:
            errors.append(err)
    else:
        errors.append(f"Class '{attr_name}' attribute must be a plain string literal")


def _check_algo_signature(node: ast.FunctionDef, errors: list[str]) -> None:
    args = [a.arg for a in node.args.args]
    if args != list(_V2_ALGO_ARGS):
        errors.append(f"algo() must be defined as algo(self, ctx) — got algo({', '.join(args)})")
    if node.args.kwonlyargs:
        errors.append("algo() must not declare keyword-only arguments")


def _ast_errors(source: str, stem: str) -> list[str]:
    errors: list[str] = []

    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return [f"Syntax error at line {exc.lineno}: {exc.msg}"]

    # Only imports, class/function definitions, and a module docstring are
    # permitted at the top level. Bare statements (calls, assignments, raises,
    # etc.) can execute arbitrary code at import time.
    for node in tree.body:
        if isinstance(node, _SAFE_TOPLEVEL):
            continue
        if (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            continue  # module-level docstring
        errors.append(f"Line {node.lineno}: executable statement at module level is not allowed")

    # Import whitelist and blocked builtins — both checked everywhere in the file
    # so a bot cannot smuggle violations inside a method body.
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if not _import_allowed(alias.name):
                    errors.append(f"Line {node.lineno}: import '{alias.name}' is not allowed")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if not _import_allowed(module):
                errors.append(f"Line {node.lineno}: import from '{module}' is not allowed")
        elif isinstance(node, ast.Call):
            func = node.func
            name = (
                func.id
                if isinstance(func, ast.Name)
                else func.attr
                if isinstance(func, ast.Attribute)
                else None
            )
            if name in _BLOCKED_BUILTINS:
                errors.append(f"Line {node.lineno}: call to '{name}' is not allowed")
        elif isinstance(node, ast.Attribute):
            if node.attr in _BLOCKED_ATTRS:
                errors.append(f"Line {node.lineno}: access to '{node.attr}' is not allowed")

    # Find the class whose name matches the filename stem (case-insensitive).
    class_node = next(
        (n for n in tree.body if isinstance(n, ast.ClassDef) and n.name.lower() == stem.lower()),
        None,
    )
    if class_node is None:
        errors.append(f"No class named '{stem}' (case-insensitive) found")
        return errors

    # Check algo method.
    algo_node = next(
        (n for n in class_node.body if isinstance(n, ast.FunctionDef) and n.name == "algo"),
        None,
    )
    if algo_node is None:
        errors.append("Player class does not define an 'algo' method")
    else:
        _check_algo_signature(algo_node, errors)

    # Check name/avatar if present as class-level attributes. Must be plain
    # string literals — dynamic values cannot be validated without execution.
    for node in class_node.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in _CLASS_STR_ATTR_VALIDATORS:
                    _check_str_literal(target.id, node.value, errors)
        elif isinstance(node, ast.AnnAssign):
            if (
                isinstance(node.target, ast.Name)
                and node.target.id in _CLASS_STR_ATTR_VALIDATORS
                and node.value is not None
            ):
                _check_str_literal(node.target.id, node.value, errors)

    return errors


# --- runtime phase (only reached after AST phase passes) ---


def _find_class_name(source: str, stem: str) -> str | None:
    """Re-parse (pure syntax, no execution) to recover the exact-case class name.

    Phase 1 (_ast_errors) already confirmed a matching class with an algo
    method exists before Phase 2 ever runs; this is a second, independent,
    cheap parse rather than threading extra return state through
    _ast_errors -- simpler to keep the two phases decoupled.
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
    return class_node.name


def _runtime_errors(
    player_file: str, class_name: str, timeout_s: float = _PROBE_TIMEOUT_S
) -> list[str]:
    """Instantiate the candidate and run one probe algo() turn inside an
    isolated worker process (WorkerPool/worker_main -- already scrubs env,
    chdirs to an ephemeral dir, and applies enforce() before import).

    This replaces the old in-process importlib.exec_module + player_class()
    + SIGALRM-guarded instantiation: that ran untrusted __init__ code (and,
    for tier-declaring bots, algo()) directly in the validator's own process,
    the exact "unguarded __init__ window" this branch closes everywhere else.

    A worker that crashes or hangs during import/instantiation/the probe call
    dies before it can report back a structured reason -- the parent only
    observes WORKER_ERROR (never-ready bootstrap, or a per-turn crash/
    timeout), so the rejection message here is deliberately less specific
    than the old differentiated messages ("crashed on import" vs "crashed
    during instantiation" vs "timed out"). The real traceback still reaches
    the CI log via the worker process's own inherited stderr.
    """
    cfg = WorkerConfig(
        player_file=str(Path(player_file).resolve()),
        player_class=class_name,
        name=class_name,
        global_random_seed=_PROBE_SEED,
    )
    with WorkerPool([cfg], timeout_s=timeout_s) as pool:
        result = pool.call(0, _PROBE_TURN)
        ready_info = pool.workers[0].ready_info

    if result is protocol.WORKER_ERROR:
        return [
            "Player crashed or timed out during isolated instantiation or probe call"
            " — see traceback above"
        ]

    # Display name/avatar validated via AST for the common literal case;
    # this runtime check is the fallback for dynamically-computed values
    # (e.g. set inside __init__). ready_info is ("ready", name, avatar) as
    # reported by the worker before its bootstrap overwrites .name with the
    # placeholder passed in via WorkerConfig.name above.
    _, live_name, live_avatar = ready_info
    if live_name is None:
        live_name = class_name  # mirrors the old getattr(..., player_class.__name__) fallback
    name_error = validate_display_name(live_name)
    if name_error:
        return [name_error]

    if live_avatar is not None:
        avatar_error = validate_avatar(live_avatar)
        if avatar_error:
            return [avatar_error]

    return []


# --- entry point ---


def validate(player_file: str) -> None:
    path = Path(player_file)
    if not path.exists():
        print(f"ERROR: File not found: {player_file}")
        sys.exit(1)

    stem = path.stem
    source = path.read_text()

    ast_errs = _ast_errors(source, stem)
    if ast_errs:
        for err in ast_errs:
            print(f"ERROR: {err}")
        sys.exit(1)

    class_name = _find_class_name(source, stem)
    if class_name is None:
        # Unreachable in practice: Phase 1 already required a matching class
        # with an algo method. Defensive only.
        print(f"ERROR: No class named '{stem}' (case-insensitive) with an 'algo' method found")
        sys.exit(1)

    runtime_errs = _runtime_errors(str(path), class_name)
    if runtime_errs:
        for err in runtime_errs:
            print(f"ERROR: {err}")
        sys.exit(1)

    print(f"OK: {stem} imported and instantiated successfully")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python -m game.validate <player_file>")
        sys.exit(1)
    validate(sys.argv[1])
