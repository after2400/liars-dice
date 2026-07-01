# Player Avatars Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the unmerged Gravatar-hash-based avatar design on `engine/player-gravatars` with a Cloudinary-based `avatar` attribute, per `docs/specs/2026-07-01-player-avatars-design.md`.

**Architecture:** An optional `avatar` class attribute (`"cloud_name/public_id.ext"`) follows the exact precedent of the existing `name` attribute: validated by `game/validate.py` (AST + runtime), read by `.github/scripts/register_player.py` on registration and `.github/scripts/lb_update_player.py` on every subsequent edit, stored as `avatar` on the player's `leaderboard.yaml` entry, and rendered by `game/components/leaderboard.py::avatar_img_tag` at 3 call sites (README standings, quarter leaderboard, local sim reports). Players without one keep getting a deterministic Gravatar-identicon fallback (unchanged from the superseded design).

**Tech Stack:** Python 3, pytest, `uv run python` (never bare `python`), Cloudinary CDN (`res.cloudinary.com`, no SDK/API calls — URLs are built as plain strings), Gravatar (fallback only).

## Global Constraints

- Always run Python via `uv run python` — never bare `python3`/`python` (see project CLAUDE.md).
- Run targeted tests with `just pytest <path>`; run `just pytest-all` before the final commit (engine-scope work, not `just pytest-players`).
- This is engine/CI work — commit messages must satisfy `.commitlintrc.mjs` (`type(scope): subject`, types/scopes from the enum lists) and end with a `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>` trailer, matching the existing commits on this branch (`git log --oneline`).
- All work happens directly on the existing branch `engine/player-gravatars` in worktree `.claude/worktrees/engine-player-gravatars` — no new worktree needed, it already exists and its baseline (350 tests) is green.
- `validate_avatar`'s format: split the `avatar` string on the **first** `/` only into `cloud_name` and `public_id_ext`. `cloud_name` must match `^[a-z0-9-]+\Z`. `public_id_ext` must match `^[A-Za-z0-9_./-]+\Z`, contain no `..`, and end in one of `png`, `jpg`, `jpeg`, `gif`, `webp` (case-sensitive, lowercase only — matches how Cloudinary actually returns extensions).
- Default render size is `64` (not `20` — confirmed by live-testing against a real Cloudinary asset during brainstorming).
- Cloudinary URL shape: `https://res.cloudinary.com/{cloud_name}/image/upload/w_{size},h_{size},c_fill/{public_id_ext}`. Gravatar fallback shape (unchanged): `https://www.gravatar.com/avatar/{synthetic_or_real_hash}?d=identicon[&f=y]&s={size}`.

---

### Task 1: `validate_avatar` in `game/validate.py`

**Files:**

- Modify: `game/validate.py:50-67` (replace the `--- gravatar rules ---` section), `game/validate.py:132-135` (`_CLASS_STR_ATTR_VALIDATORS`), `game/validate.py:229-242` (AST-phase comment, unchanged logic — just confirm it still works via the dict), `game/validate.py:323-327` (runtime-phase check)
- Test: `tests/test_validate_player.py:294-389` (replace the `gravatar` test section)

**Interfaces:**

- Produces: `validate_avatar(value: str) -> str | None` in `game/validate.py`, replacing `validate_gravatar_hash`. Consumed by Task 3 (`register_player.py`) and Task 4 (`lb_update_player.py`).

- [ ] **Step 1: Write the failing tests**

Replace lines 294-389 of `tests/test_validate_player.py` (the entire `gravatar` test section, from `def test_gravatar_valid_md5_passes` through the end of `test_gravatar_trailing_newline_fails`) with:

```python
def test_avatar_valid_passes(tmp_path):
    """A well-formed cloud_name/public_id.ext avatar passes validation."""
    f = tmp_path / "hasavatar.py"
    f.write_text(
        "class Hasavatar:\n"
        "    avatar = 'hdyiihba/The_Merovingian_200x200_rqd12y.png'\n"
        "    def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):\n"
        "        return None\n"
    )
    result = _run(f)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK" in result.stdout


def test_avatar_missing_slash_fails(tmp_path):
    """An avatar string with no '/' separating cloud_name from public_id exits 1."""
    f = tmp_path / "badavatar.py"
    f.write_text(
        "class Badavatar:\n"
        "    avatar = 'no-slash-here'\n"
        "    def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):\n"
        "        return None\n"
    )
    result = _run(f)
    assert result.returncode == 1
    assert "ERROR" in result.stdout
    assert "avatar" in result.stdout.lower()


def test_avatar_bad_cloud_name_fails(tmp_path):
    """Uppercase or invalid characters in cloud_name exit 1."""
    f = tmp_path / "badavatar.py"
    f.write_text(
        "class Badavatar:\n"
        "    avatar = 'BadCloud/public_id.png'\n"
        "    def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):\n"
        "        return None\n"
    )
    result = _run(f)
    assert result.returncode == 1
    assert "ERROR" in result.stdout


def test_avatar_bad_public_id_fails(tmp_path):
    """Disallowed characters (e.g. a space) in public_id exit 1."""
    f = tmp_path / "badavatar.py"
    f.write_text(
        "class Badavatar:\n"
        "    avatar = 'hdyiihba/has a space.png'\n"
        "    def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):\n"
        "        return None\n"
    )
    result = _run(f)
    assert result.returncode == 1
    assert "ERROR" in result.stdout


def test_avatar_dotdot_rejected(tmp_path):
    """A '..' path segment in public_id exits 1."""
    f = tmp_path / "badavatar.py"
    f.write_text(
        "class Badavatar:\n"
        "    avatar = 'hdyiihba/../secret.png'\n"
        "    def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):\n"
        "        return None\n"
    )
    result = _run(f)
    assert result.returncode == 1
    assert "ERROR" in result.stdout


def test_avatar_disallowed_extension_fails(tmp_path):
    """An .svg extension exits 1 (raster formats only)."""
    f = tmp_path / "badavatar.py"
    f.write_text(
        "class Badavatar:\n"
        "    avatar = 'hdyiihba/public_id.svg'\n"
        "    def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):\n"
        "        return None\n"
    )
    result = _run(f)
    assert result.returncode == 1
    assert "ERROR" in result.stdout


def test_avatar_missing_extension_fails(tmp_path):
    """A public_id with no extension at all exits 1."""
    f = tmp_path / "badavatar.py"
    f.write_text(
        "class Badavatar:\n"
        "    avatar = 'hdyiihba/public_id'\n"
        "    def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):\n"
        "        return None\n"
    )
    result = _run(f)
    assert result.returncode == 1
    assert "ERROR" in result.stdout


def test_avatar_absent_is_valid(tmp_path):
    """No avatar attribute at all is perfectly valid (optional)."""
    f = tmp_path / "noavatar.py"
    f.write_text(
        "class Noavatar:\n"
        "    def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):\n"
        "        return None\n"
    )
    result = _run(f)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK" in result.stdout


def test_avatar_trailing_newline_fails(tmp_path):
    """An avatar value with a trailing newline exits 1 — '\\Z' must not match before a trailing newline."""
    f = tmp_path / "badavatar.py"
    f.write_text(
        "class Badavatar:\n"
        "    avatar = 'hdyiihba/public_id.png\\n'\n"
        "    def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):\n"
        "        return None\n"
    )
    result = _run(f)
    assert result.returncode == 1
    assert "ERROR" in result.stdout


def test_avatar_folder_nested_public_id_passes(tmp_path):
    """A public_id containing folder slashes (legal in Cloudinary) passes validation."""
    f = tmp_path / "hasavatar.py"
    f.write_text(
        "class Hasavatar:\n"
        "    avatar = 'hdyiihba/players/merovingian.png'\n"
        "    def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):\n"
        "        return None\n"
    )
    result = _run(f)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK" in result.stdout
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `just pytest tests/test_validate_player.py -k avatar -v`
Expected: FAIL — `AttributeError` or similar, since `validate_avatar` doesn't exist yet and the `avatar` class attribute isn't recognized (the AST/runtime phases still only know about `gravatar`, so these player files pass through unvalidated — most will incorrectly PASS instead of FAIL, or the ones testing rejection will fail because nothing rejects them). Confirm each new test fails or behaves incorrectly before implementing.

- [ ] **Step 3: Replace `validate_gravatar_hash` with `validate_avatar`**

Replace lines 50-67 of `game/validate.py` (the `--- gravatar rules ---` section) with:

```python
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
```

- [ ] **Step 4: Update `_CLASS_STR_ATTR_VALIDATORS`**

In `game/validate.py`, change (around line 132-135):

```python
_CLASS_STR_ATTR_VALIDATORS = {
    "name": validate_display_name,
    "gravatar": validate_gravatar_hash,
}
```

to:

```python
_CLASS_STR_ATTR_VALIDATORS = {
    "name": validate_display_name,
    "avatar": validate_avatar,
}
```

(No other change needed in `_ast_errors` — it already iterates `_CLASS_STR_ATTR_VALIDATORS` generically. The comment on line 229, `# Check name/gravatar if present...`, should be updated to say `name/avatar` for accuracy.)

- [ ] **Step 5: Update the runtime-phase check**

In `game/validate.py`, change (around line 323-327):

```python
    gravatar = getattr(player_class, "gravatar", None)
    if gravatar is not None:
        gravatar_error = validate_gravatar_hash(gravatar)
        if gravatar_error:
            return [gravatar_error]
```

to:

```python
    avatar = getattr(player_class, "avatar", None)
    if avatar is not None:
        avatar_error = validate_avatar(avatar)
        if avatar_error:
            return [avatar_error]
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `just pytest tests/test_validate_player.py -v`
Expected: PASS — all tests in the file, including the new `avatar` ones and every pre-existing test (`test_valid_player`, `test_name_too_long`, etc., which must be unaffected).

- [ ] **Step 7: Commit**

```bash
git add game/validate.py tests/test_validate_player.py
git commit -m "$(cat <<'EOF'
feat(engine): replace validate_gravatar_hash with validate_avatar

Gravatar's one-avatar-per-account limit doesn't work for authors with
multiple bots. Cloudinary lets one free account host unlimited images,
so the avatar attribute is now a "cloud_name/public_id.ext" identifier
instead of an email hash.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: `avatar_img_tag` in `game/components/leaderboard.py`

**Files:**

- Modify: `game/components/leaderboard.py:46-64` (replace `_GRAVATAR_BASE`/`gravatar_img_tag`)
- Test: `tests/test_leaderboard.py:446-500` (replace the `gravatar_img_tag` test section)

**Interfaces:**

- Produces: `avatar_img_tag(class_name: str, player: dict, size: int = 64) -> str` in `game/components/leaderboard.py`, replacing `gravatar_img_tag`. Consumed by Task 5 (`run_season.py`) and Task 6 (`quarter.py`).

- [ ] **Step 1: Write the failing tests**

Replace lines 446-500 of `tests/test_leaderboard.py` (from `# --- gravatar_img_tag ---` through the end of `test_gravatar_img_tag_default_size_is_20`) with:

```python
# --- avatar_img_tag ---


def test_avatar_img_tag_uses_cloudinary_when_avatar_set():
    from game.components.leaderboard import avatar_img_tag

    player = {"avatar": "hdyiihba/The_Merovingian_200x200_rqd12y.png"}
    tag = avatar_img_tag("Merovingian", player)
    assert (
        'src="https://res.cloudinary.com/hdyiihba/image/upload/'
        'w_64,h_64,c_fill/The_Merovingian_200x200_rqd12y.png"' in tag
    )


def test_avatar_img_tag_falls_back_to_gravatar_when_absent():
    import hashlib

    from game.components.leaderboard import avatar_img_tag

    player = {}
    tag = avatar_img_tag("Alice", player)
    synthetic_hash = hashlib.md5(b"Alice", usedforsecurity=False).hexdigest()
    assert f'src="https://www.gravatar.com/avatar/{synthetic_hash}?d=identicon&f=y&s=64"' in tag


def test_avatar_img_tag_fallback_is_deterministic():
    from game.components.leaderboard import avatar_img_tag

    tag1 = avatar_img_tag("Alice", {})
    tag2 = avatar_img_tag("Alice", {})
    assert tag1 == tag2


def test_avatar_img_tag_fallback_differs_per_class_name():
    from game.components.leaderboard import avatar_img_tag

    tag_alice = avatar_img_tag("Alice", {})
    tag_bruno = avatar_img_tag("Bruno", {})
    assert tag_alice != tag_bruno


def test_avatar_img_tag_respects_size_param_for_cloudinary():
    from game.components.leaderboard import avatar_img_tag

    player = {"avatar": "hdyiihba/The_Merovingian_200x200_rqd12y.png"}
    tag = avatar_img_tag("Merovingian", player, size=32)
    assert "w_32,h_32,c_fill" in tag
    assert 'width="32" height="32"' in tag


def test_avatar_img_tag_respects_size_param_for_gravatar_fallback():
    from game.components.leaderboard import avatar_img_tag

    tag = avatar_img_tag("Alice", {}, size=32)
    assert "s=32" in tag
    assert 'width="32" height="32"' in tag


def test_avatar_img_tag_default_size_is_64():
    from game.components.leaderboard import avatar_img_tag

    tag = avatar_img_tag("Alice", {})
    assert 'width="64" height="64"' in tag
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `just pytest tests/test_leaderboard.py -k avatar_img_tag -v`
Expected: FAIL with `ImportError: cannot import name 'avatar_img_tag'`.

- [ ] **Step 3: Replace `gravatar_img_tag` with `avatar_img_tag`**

Replace lines 46-64 of `game/components/leaderboard.py` (from `_GRAVATAR_BASE = ...` through the end of `gravatar_img_tag`) with:

```python
_GRAVATAR_BASE = "https://www.gravatar.com/avatar"
_CLOUDINARY_BASE = "https://res.cloudinary.com"


def avatar_img_tag(class_name: str, player: dict, size: int = 64) -> str:
    """Build an <img> tag for a player's avatar.

    Uses the player's own Cloudinary image if `avatar` ("cloud_name/public_id.ext")
    is set. Otherwise falls back to a Gravatar identicon keyed off a hash of the
    (immutable, unique) class name so every player still gets a distinct, stable
    placeholder; `f=y` forces the identicon even in the astronomically unlikely
    case that hash coincidentally matches a real Gravatar account.
    """
    avatar = player.get("avatar")
    if avatar:
        cloud_name, public_id_ext = avatar.split("/", 1)
        url = f"{_CLOUDINARY_BASE}/{cloud_name}/image/upload/w_{size},h_{size},c_fill/{public_id_ext}"
    else:
        synthetic_hash = hashlib.md5(class_name.encode("utf-8"), usedforsecurity=False).hexdigest()
        url = f"{_GRAVATAR_BASE}/{synthetic_hash}?d=identicon&f=y&s={size}"
    return f'<img src="{url}" width="{size}" height="{size}">'
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `just pytest tests/test_leaderboard.py -v`
Expected: PASS — all tests in the file.

- [ ] **Step 5: Commit**

```bash
git add game/components/leaderboard.py tests/test_leaderboard.py
git commit -m "$(cat <<'EOF'
feat(engine): render Cloudinary avatars, default size 64

Replaces gravatar_img_tag with avatar_img_tag: renders the player's own
Cloudinary image when avatar is set, otherwise keeps the deterministic
Gravatar-identicon fallback. Default size bumped from 20 to 64 after
live-testing both against a real Cloudinary asset — 64 reads far better
in a markdown table cell.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: `register_player.py` stores `avatar`

**Files:**

- Modify: `.github/scripts/register_player.py:56` (import), `:94-99` (validation), `:120-121` (storage)
- Test: `tests/test_register_player.py:234-265` (replace the `gravatar` test section)

**Interfaces:**

- Consumes: `validate_avatar(value: str) -> str | None` from `game/validate.py` (Task 1).

- [ ] **Step 1: Write the failing tests**

Replace lines 234-265 of `tests/test_register_player.py` (from `def test_register_stores_gravatar_hash` through the end of `test_register_rejects_invalid_gravatar_hash`) with:

```python
def test_register_stores_avatar(tmp_path):
    player_py = tmp_path / "hasavatar.py"
    player_py.write_text(
        "class Hasavatar:\n"
        "    avatar = 'hdyiihba/The_Merovingian_200x200_rqd12y.png'\n"
        "    def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):\n"
        "        return None\n"
    )
    lb = {"total_runs": 0, "players": {}}
    rc, out = run_register(str(player_py), lb, tmp_path)
    assert rc == 0, out
    lb_result = yaml.safe_load((tmp_path / "leaderboard.yaml").read_text())
    assert (
        lb_result["players"]["Hasavatar"]["avatar"]
        == "hdyiihba/The_Merovingian_200x200_rqd12y.png"
    )


def test_register_omits_avatar_when_not_set(tmp_path):
    lb = {"total_runs": 0, "players": {}}
    player_file = REPO_ROOT / "players" / "alice.py"
    rc, out = run_register(player_file, lb, tmp_path)
    assert rc == 0, out
    lb_result = yaml.safe_load((tmp_path / "leaderboard.yaml").read_text())
    assert "avatar" not in lb_result["players"]["Alice"]


def test_register_rejects_invalid_avatar(tmp_path):
    player_py = tmp_path / "badavatar.py"
    player_py.write_text("class Badavatar:\n    avatar = 'not-a-valid-avatar'\n")
    lb = {"total_runs": 0, "players": {}}
    rc, out = run_register(str(player_py), lb, tmp_path)
    assert rc == 1, out
    assert "ERROR" in out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `just pytest tests/test_register_player.py -k avatar -v`
Expected: FAIL — `register_player.py` still imports `validate_gravatar_hash` and reads the `gravatar` attribute, so `avatar` is silently ignored and never written to the leaderboard; `test_register_rejects_invalid_avatar` fails because nothing rejects it (`avatar` isn't checked at all).

- [ ] **Step 3: Update the import**

In `.github/scripts/register_player.py`, change line 56:

```python
    from game.validate import validate_display_name, validate_gravatar_hash
```

to:

```python
    from game.validate import validate_avatar, validate_display_name
```

- [ ] **Step 4: Update the validation block**

Change lines 94-99:

```python
    gravatar = getattr(player_class, "gravatar", None)
    if gravatar is not None:
        gravatar_error = validate_gravatar_hash(gravatar)
        if gravatar_error:
            print(f"ERROR: {gravatar_error}")
            sys.exit(1)
```

to:

```python
    avatar = getattr(player_class, "avatar", None)
    if avatar is not None:
        avatar_error = validate_avatar(avatar)
        if avatar_error:
            print(f"ERROR: {avatar_error}")
            sys.exit(1)
```

- [ ] **Step 5: Update the storage block**

Change lines 120-121:

```python
    if gravatar is not None:
        players[class_name]["gravatar_hash"] = gravatar
```

to:

```python
    if avatar is not None:
        players[class_name]["avatar"] = avatar
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `just pytest tests/test_register_player.py -v`
Expected: PASS — all tests in the file.

- [ ] **Step 7: Commit**

```bash
git add .github/scripts/register_player.py tests/test_register_player.py
git commit -m "$(cat <<'EOF'
feat(scripts): store avatar (not gravatar_hash) on player registration

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: `lb_update_player.py` syncs `avatar`

**Files:**

- Modify: `.github/scripts/lb_update_player.py` (docstring, import, validation, storage/removal, print message)
- Test: `tests/test_lb_update_player.py:39-79` (replace the `gravatar` test section; leave `test_display_name_still_updates` and `test_player_not_in_leaderboard_warns` untouched)

**Interfaces:**

- Consumes: `validate_avatar(value: str) -> str | None` from `game/validate.py` (Task 1).

- [ ] **Step 1: Write the failing tests**

Replace lines 39-79 of `tests/test_lb_update_player.py` (from `def test_sets_gravatar_hash_on_new_attribute` through the end of `test_rejects_invalid_gravatar_hash`) with:

```python
def test_sets_avatar_on_new_attribute(tmp_path):
    player_file = tmp_path / "topper.py"
    player_file.write_text(
        "class Topper:\n"
        "    avatar = 'hdyiihba/The_Merovingian_200x200_rqd12y.png'\n"
        "    def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):\n"
        "        return None\n"
    )
    result = _run(player_file, _base_lb(), tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    lb = yaml.safe_load((tmp_path / "leaderboard.yaml").read_text())
    assert lb["players"]["Topper"]["avatar"] == "hdyiihba/The_Merovingian_200x200_rqd12y.png"


def test_removes_avatar_when_attribute_removed(tmp_path):
    player_file = tmp_path / "topper.py"
    player_file.write_text(
        "class Topper:\n"
        "    def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):\n"
        "        return None\n"
    )
    lb = _base_lb()
    lb["players"]["Topper"]["avatar"] = "hdyiihba/The_Merovingian_200x200_rqd12y.png"
    result = _run(player_file, lb, tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    updated = yaml.safe_load((tmp_path / "leaderboard.yaml").read_text())
    assert "avatar" not in updated["players"]["Topper"]


def test_rejects_invalid_avatar(tmp_path):
    player_file = tmp_path / "topper.py"
    player_file.write_text(
        "class Topper:\n"
        "    avatar = 'not-a-valid-avatar'\n"
        "    def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):\n"
        "        return None\n"
    )
    result = _run(player_file, _base_lb(), tmp_path)
    assert result.returncode == 1
    assert "ERROR" in result.stdout + result.stderr
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `just pytest tests/test_lb_update_player.py -v`
Expected: FAIL on the 3 new/renamed tests — `lb_update_player.py` still reads/writes `gravatar`/`gravatar_hash`, so `avatar` is never synced and invalid `avatar` values are never rejected. `test_display_name_still_updates` and `test_player_not_in_leaderboard_warns` should still PASS (they don't touch avatars).

- [ ] **Step 3: Update the script**

Rewrite `.github/scripts/lb_update_player.py` in full:

```python
#!/usr/bin/env python3
"""Validate a modified player file and sync display_name/avatar in leaderboard.yaml.

Usage: lb_update_player.py <player_file>
Exits 0 on success (prints updated line or no-change line).
Exits 1 on validation failure (prints ERROR line).
"""

import importlib.util
import sys
from pathlib import Path

import yaml

# Ensure the repo root is importable so 'game' (used here and by player files) resolves.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from game.validate import validate_avatar, validate_display_name  # noqa: E402

player_file = sys.argv[1]
p = Path(player_file)

spec = importlib.util.spec_from_file_location(p.stem, p)
if spec is None or spec.loader is None:
    print(f"ERROR: Cannot load {player_file}")
    sys.exit(1)
m = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(m)
except Exception as e:
    print(f"ERROR: Failed to import {player_file}: {e}")
    sys.exit(1)

cls = next(
    (
        getattr(m, n)
        for n in dir(m)
        if n.lower() == p.stem.lower() and isinstance(getattr(m, n), type)
    ),
    None,
)
if cls is None:
    print(f"ERROR: No class matching {p.stem} found")
    sys.exit(1)

class_name = cls.__name__
display_name = getattr(cls, "name", class_name)

name_error = validate_display_name(display_name)
if name_error:
    print(f"ERROR: {name_error}")
    sys.exit(1)

avatar = getattr(cls, "avatar", None)
if avatar is not None:
    avatar_error = validate_avatar(avatar)
    if avatar_error:
        print(f"ERROR: {avatar_error}")
        sys.exit(1)

with open("leaderboard.yaml") as f:
    data = yaml.safe_load(f) or {}

if class_name in data.get("players", {}):
    data["players"][class_name]["display_name"] = display_name
    if avatar is not None:
        data["players"][class_name]["avatar"] = avatar
    else:
        data["players"][class_name].pop("avatar", None)
    with open("leaderboard.yaml", "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)
    print(f"Updated {class_name}: display_name='{display_name}', avatar={avatar!r}")
else:
    print(f"WARNING: {class_name} not found in leaderboard; no update made")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `just pytest tests/test_lb_update_player.py -v`
Expected: PASS — all 5 tests in the file (3 avatar tests + the 2 untouched ones).

- [ ] **Step 5: Commit**

```bash
git add .github/scripts/lb_update_player.py tests/test_lb_update_player.py
git commit -m "$(cat <<'EOF'
feat(scripts): sync avatar (not gravatar_hash) on player-file edits

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: Render Cloudinary avatars in `run_season.py`

**Files:**

- Modify: `.github/scripts/run_season.py:394`, `:432` (`_standings_table`), `:451`, `:466` (`_quarter_leaderboard_table`)
- Test: `tests/test_run_season.py:299-306` (width/height assertion)

**Interfaces:**

- Consumes: `avatar_img_tag(class_name: str, player: dict, size: int = 64) -> str` from `game/components/leaderboard.py` (Task 2).

- [ ] **Step 1: Update the failing assertion**

In `tests/test_run_season.py`, change line 306:

```python
    assert 'width="20" height="20"' in data_row
```

to:

```python
    assert 'width="64" height="64"' in data_row
```

- [ ] **Step 2: Run test to verify it fails**

Run: `just pytest tests/test_run_season.py::test_standings_table_includes_avatar_img_tag -v`
Expected: FAIL — `_standings_table` still calls `gravatar_img_tag`, whose default size is `20`, not `64`.

- [ ] **Step 3: Update both call sites**

In `.github/scripts/run_season.py`, change line 394:

```python
    from game.components.leaderboard import gravatar_img_tag
```

to:

```python
    from game.components.leaderboard import avatar_img_tag
```

Change line 432:

```python
        display = f"{gravatar_img_tag(name, p)} {display_names.get(name, name)}"
```

to:

```python
        display = f"{avatar_img_tag(name, p)} {display_names.get(name, name)}"
```

Inside `_quarter_leaderboard_table`, change line 451:

```python
    from game.components.leaderboard import gravatar_img_tag
```

to:

```python
    from game.components.leaderboard import avatar_img_tag
```

Change line 466:

```python
        display = f"{gravatar_img_tag(name, p)} {display_names.get(name, name)}"
```

to:

```python
        display = f"{avatar_img_tag(name, p)} {display_names.get(name, name)}"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `just pytest tests/test_run_season.py -v`
Expected: PASS — all tests in the file, including `test_standings_table_includes_avatar_img_tag` and `test_quarter_leaderboard_includes_avatar_img_tag`.

- [ ] **Step 5: Commit**

```bash
git add .github/scripts/run_season.py tests/test_run_season.py
git commit -m "$(cat <<'EOF'
feat(scripts): render avatar_img_tag in standings tables

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: Render Cloudinary avatars in `game/simulation/quarter.py`

**Files:**

- Modify: `game/simulation/quarter.py:122`, `:162`
- Test: `tests/test_simulate_quarter.py:326-347` (width/height assertion)

**Interfaces:**

- Consumes: `avatar_img_tag(class_name: str, player: dict, size: int = 64) -> str` from `game/components/leaderboard.py` (Task 2).

- [ ] **Step 1: Update the failing assertion**

In `tests/test_simulate_quarter.py`, change line 347:

```python
    assert 'width="20" height="20"' in text
```

to:

```python
    assert 'width="64" height="64"' in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `just pytest tests/test_simulate_quarter.py::test_write_report_includes_avatar_img_tag -v`
Expected: FAIL — `write_report` still calls `gravatar_img_tag`, default size `20`.

- [ ] **Step 3: Update the call site**

In `game/simulation/quarter.py`, change line 122:

```python
    from game.components.leaderboard import build_display_names, gravatar_img_tag
```

to:

```python
    from game.components.leaderboard import avatar_img_tag, build_display_names
```

Change line 162:

```python
                display = f"{gravatar_img_tag(name, p)} {display_names.get(name, name)}"
```

to:

```python
                display = f"{avatar_img_tag(name, p)} {display_names.get(name, name)}"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `just pytest tests/test_simulate_quarter.py -v`
Expected: PASS — all tests in the file.

- [ ] **Step 5: Commit**

```bash
git add game/simulation/quarter.py tests/test_simulate_quarter.py
git commit -m "$(cat <<'EOF'
feat(game): render avatar_img_tag in quarter simulation reports

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: Docs — Player-Guide and README

**Files:**

- Modify: `docs/wiki/Player-Guide.md:19`, `:26`, `:44`
- Modify: `README.md:160`

**Interfaces:** None — docs only.

- [ ] **Step 1: Rewrite the Player-Guide avatar bullet and example**

In `docs/wiki/Player-Guide.md`, change line 19:

```
5. Optionally set a `gravatar` attribute (avatar shown on standings tables — see below)
```

to:

```
5. Optionally set an `avatar` attribute (image shown on standings tables — see below)
```

Change the code block (lines 21-32):

```python
from game.components.bets import Bet

class Fred:
    name = "Fred the Magnificent"  # optional — defaults to class name
    gravatar = "205e460b479e2e5b48aec07710c08d50"  # optional — Gravatar hash

    def algo(self, ctx) -> Bet | None:
        # ctx.hand, ctx.prior_bet, ctx.total_dice, ctx.bet_history,
        # ctx.outcomes, ctx.stats, ctx.tier, ctx.round_players
        ...
```

to:

```python
from game.components.bets import Bet

class Fred:
    name = "Fred the Magnificent"  # optional — defaults to class name
    avatar = "hdyiihba/The_Merovingian_200x200_rqd12y.png"  # optional — see below

    def algo(self, ctx) -> Bet | None:
        # ctx.hand, ctx.prior_bet, ctx.total_dice, ctx.bet_history,
        # ctx.outcomes, ctx.stats, ctx.tier, ctx.round_players
        ...
```

Change the **Avatars** paragraph (line 44):

```
**Avatars:** `gravatar` must be a Gravatar hash — an MD5 (32 lowercase hex chars) or SHA256 (64 lowercase hex chars) hash of the email address tied to your Gravatar account, **not** an email address or arbitrary URL. See [Gravatar's hashing instructions](https://docs.gravatar.com/api/avatars/hash/) to generate one. Players without a `gravatar` get a distinct, automatically-generated placeholder image instead — no image ever needs to be uploaded anywhere in this repo.
```

to:

```
**Avatars:** sign up for a free [Cloudinary](https://cloudinary.com) account and upload an image — one account can host images for as many bots as you own, unlike Gravatar. Cloudinary shows you the image's full delivery URL, e.g.:

```

https://res.cloudinary.com/hdyiihba/image/upload/The_Merovingian_200x200_rqd12y.png
└───┬────┘ └──────────────┬───────────────┘
cloud_name public_id.ext

avatar = "hdyiihba/The_Merovingian_200x200_rqd12y.png"

```

Your `avatar` attribute is everything after `.../image/upload/` — `cloud_name` joined to `public_id.ext` by the `/` that already separates them in the URL. Must end in `.png`, `.jpg`, `.jpeg`, `.gif`, or `.webp`. Players without an `avatar` get a distinct, automatically-generated Gravatar placeholder image instead — no image ever needs to be uploaded anywhere for players who don't want a custom one.
```

- [ ] **Step 2: Update the README script listing**

In `README.md`, change line 160:

```
    lb_update_player.py  # validates and updates display_name/gravatar_hash on modification
```

to:

```
    lb_update_player.py  # validates and updates display_name/avatar on modification
```

- [ ] **Step 3: Commit**

```bash
git add docs/wiki/Player-Guide.md README.md
git commit -m "$(cat <<'EOF'
docs: document the Cloudinary avatar attribute, not Gravatar

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 8: Final verification and cleanup

**Files:**

- Delete: `docs/specs/2026-07-01-player-gravatars-design.md` (superseded by `2026-07-01-player-avatars-design.md`, already committed)
- Delete: `docs/plans/2026-07-01-player-gravatars.md` (superseded by this plan)

**Interfaces:** None — verification and repo hygiene only.

- [ ] **Step 1: Grep for any remaining `gravatar` references outside historical/superseded docs**

Run:

```bash
grep -rni "gravatar" --include="*.py" --include="*.yml" --include="*.yaml" .
```

Expected: only matches inside `game/components/leaderboard.py` (the `_GRAVATAR_BASE`/Gravatar-fallback code, which is intentional and correct — the fallback still uses Gravatar) and `game/validate.py` module docstrings if any remain. No `gravatar_hash`, `validate_gravatar_hash`, or `gravatar_img_tag` should appear anywhere. If any do, fix them before proceeding.

- [ ] **Step 2: Delete the superseded design/plan docs**

```bash
git rm docs/specs/2026-07-01-player-gravatars-design.md docs/plans/2026-07-01-player-gravatars.md
```

- [ ] **Step 3: Run the full test suite**

Run: `just pytest-all`
Expected: PASS — all tests (350+ from baseline, plus the new/renamed avatar tests, minus the removed ones — net count will differ slightly from the original 350 baseline since some old gravatar-specific tests were replaced 1:1 or expanded with a few extra edge cases in Task 1).

- [ ] **Step 4: Commit the cleanup**

```bash
git commit -m "$(cat <<'EOF'
chore(docs): remove superseded gravatar-hash design and plan docs

Both are fully replaced by 2026-07-01-player-avatars-design.md and this
plan; keeping them around would leave two conflicting specs in the repo.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 5: Confirm final branch state**

Run: `git log --oneline main..engine/player-gravatars` and `git status`
Expected: a clean working tree, and a commit history that tells a coherent story (original Gravatar-hash commits, followed by the design-doc revision, followed by this plan's Cloudinary-conversion commits). Report back to the user for review before opening a PR — do not push or open a PR without explicit approval.
