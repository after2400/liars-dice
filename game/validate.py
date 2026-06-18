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
import importlib.util
import inspect
import sys
from pathlib import Path

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
        "game.components.stats",
    }
)


def _import_allowed(module: str) -> bool:
    if module.startswith("game"):
        return module in _ALLOWED_GAME_MODULES
    return module.split(".")[0] in _ALLOWED_STDLIB


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

_REQUIRED_ALGO_ARGS = ("self", "hand", "prior_bet", "total_dice", "bet_history", "outcomes")
_ALLOWED_OPT_ARGS: frozenset[str] = frozenset({"stats", "tier"})


def _check_algo_signature(node: ast.FunctionDef, errors: list[str]) -> None:
    args = [a.arg for a in node.args.args]
    for i, expected in enumerate(_REQUIRED_ALGO_ARGS):
        actual = args[i] if i < len(args) else "<missing>"
        if actual != expected:
            errors.append(f"algo() argument {i} must be '{expected}', got '{actual}'")
    for name in args[len(_REQUIRED_ALGO_ARGS) :]:
        if name not in _ALLOWED_OPT_ARGS:
            errors.append(f"algo() has unexpected positional argument '{name}'")
    for kw in node.args.kwonlyargs:
        if kw.arg not in _ALLOWED_OPT_ARGS:
            errors.append(f"algo() has unexpected keyword-only argument '{kw.arg}'")


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

    # Check display name if present as a class-level attribute. Must be a plain
    # string literal — dynamic values cannot be validated without execution.
    for node in class_node.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "name":
                    if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                        err = validate_display_name(node.value.value)
                        if err:
                            errors.append(err)
                    else:
                        errors.append("Class 'name' attribute must be a plain string literal")
        elif isinstance(node, ast.AnnAssign):
            if (
                isinstance(node.target, ast.Name)
                and node.target.id == "name"
                and node.value is not None
            ):
                if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                    err = validate_display_name(node.value.value)
                    if err:
                        errors.append(err)
                else:
                    errors.append("Class 'name' attribute must be a plain string literal")

    return errors


# --- runtime phase (only reached after AST phase passes) ---


def _runtime_errors(player_file: str, stem: str) -> list[str]:
    spec = importlib.util.spec_from_file_location(stem, player_file)
    if spec is None or spec.loader is None:
        return [f"Could not create module spec for {player_file}"]

    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        return [f"Player file crashed on import: {type(exc).__name__}: {exc}"]

    player_class = next(
        (
            getattr(module, name)
            for name in dir(module)
            if name.lower() == stem.lower() and isinstance(getattr(module, name), type)
        ),
        None,
    )
    if player_class is None:
        return [f"No class named '{stem}' (case-insensitive) found after import"]

    try:
        instance = player_class()
    except Exception as exc:
        return [f"Player class crashed during instantiation: {type(exc).__name__}: {exc}"]

    if not callable(getattr(instance, "algo", None)):
        return ["Player class does not define an 'algo' method"]

    if "tier" in inspect.signature(instance.algo).parameters:
        try:
            instance.algo([], None, 10, [], [], tier=None)
        except Exception as exc:
            return [f"algo() raised {type(exc).__name__} when called with tier=None: {exc}"]

    # Display name validated via AST; runtime check covers dynamic names set
    # outside of a plain class-level assignment.
    display_name = getattr(player_class, "name", player_class.__name__)
    name_error = validate_display_name(display_name)
    if name_error:
        return [name_error]

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

    runtime_errs = _runtime_errors(str(path), stem)
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
