# Player Avatars — Design

Supersedes `2026-07-01-player-gravatars-design.md` (never merged). That design
committed to Gravatar specifically; it turned out Gravatar allows only one
avatar per email account, which doesn't work for an author who owns multiple
player bots (they'd need a separate Gravatar account per bot). This revision
keeps the same shape but moves the opt-in image to Cloudinary, where one free
account can host unlimited distinct images.

## Goal

Let a player author optionally set an avatar image on their bot, and render a
small image next to their name everywhere standings are shown: README
standings tables, the season summary posted to the GitHub tracking issue, and
local `sim-*.md` quarter-simulation reports. Players who don't set one still
get a distinct, consistent placeholder image so tables stay visually uniform.

## Background

Player display names already follow a validated class-attribute pattern:
`name = "Alice"` on the player class, checked in two phases by
`game/validate.py` (`validate_display_name`, AST + runtime), read at
registration by `.github/scripts/register_player.py`, and re-synced on every
subsequent edit to that player's file by `.github/scripts/lb_update_player.py`
(triggered by `update-leaderboard.yml` on any `players/*.py` push to `main`).
This design adds an `avatar` attribute that follows the identical shape, so no
new CI workflow is needed.

Per the project's player-PR-scope rule, a player PR touches exactly one file
(`players/<name>.py`); `leaderboard.yaml` is CI-managed and never hand-edited.
The `avatar` attribute must therefore live on the player class, not in the
leaderboard file directly — the existing registration/sync scripts write it
into `leaderboard.yaml` the same way they already do for `display_name`.

We commit to Cloudinary specifically (not an arbitrary avatar URL) so the
attribute can be a short `cloud_name/public_id.ext` identifier rather than a
full URL, and the delivery URL is always built by our own code with a
hardcoded `https://res.cloudinary.com/` prefix. Because the host is a literal
in our code — never derived from player-supplied data — no player-controlled
string can ever redirect the `<img>` tag off Cloudinary's domain, regardless
of its content. This sidesteps the same class of problems arbitrary URLs
would raise in a public repo (SSRF, hotlinking to arbitrary hosts, tracking
pixels): the identifier alone can only ever resolve to `res.cloudinary.com`.

Each author brings their own free Cloudinary account. A single account can
host unlimited images, so one author with several bots just uploads one image
per bot and references each by its own `public_id` — no per-bot account
needed, unlike Gravatar.

## The Rule

### Player-facing API

An optional class-level string attribute, `avatar`, following the exact
precedent of `name`:

```python
class Merovingian:
    name = "The Merovingian"
    avatar = "hdyiihba/The_Merovingian_200x200_rqd12y.png"  # cloud_name/public_id.ext
```

Omitted entirely if the author doesn't want one — no change required to any
existing player file.

The value is copied directly from the asset's Cloudinary delivery URL: given
`https://res.cloudinary.com/hdyiihba/image/upload/The_Merovingian_200x200_rqd12y.png`,
the attribute is everything after `.../upload/` — cloud name and public ID
(with extension), joined by the single `/` that already separates them in the
URL.

### Validation (`game/validate.py`)

New `validate_avatar(value: str) -> str | None`, alongside
`validate_display_name` (replaces `validate_gravatar_hash`):

- Split on the first `/` only (`value.split("/", 1)`) into `cloud_name` and
  `public_id_ext`. Missing `/` → error.
- `cloud_name` must match `^[a-z0-9-]+$` (Cloudinary's own cloud-name
  charset).
- `public_id_ext` must match `^[A-Za-z0-9_./-]+$` — alphanumerics, `_`, `-`,
  `.`, and `/` (folder-nested public IDs are legal in Cloudinary), no other
  characters. No `..` path segments.
- The extension (text after the last `.` in `public_id_ext`) must be one of
  `png`, `jpg`, `jpeg`, `gif`, `webp` — no `svg`, no extension-less value.
- No network call — format-only, matching every other `validate_*` check.
- Enforced in both phases, mirroring the `name` checks:
  - **AST phase**: if the matching class defines an `avatar` class attribute,
    it must be a plain string literal and must pass `validate_avatar`.
  - **Runtime phase**: `getattr(player_class, "avatar", None)` re-checked
    after instantiation.
- Attribute absent → valid (optional, no error).

### Rendering & fallback

New `avatar_img_tag(class_name: str, player: dict, size: int = 64) -> str` in
`game/components/leaderboard.py` (replaces `gravatar_img_tag`), next to
`build_display_names` (same shape: takes the raw per-player leaderboard
dict). Returns an `<img src="..." width="{size}" height="{size}">` string:

- **`avatar` present** (stored in the leaderboard entry, see schema below):
  split into `cloud_name` / `public_id_ext`, build
  `https://res.cloudinary.com/{cloud_name}/image/upload/w_{size},h_{size},c_fill/{public_id_ext}`.
  Confirmed working end-to-end against a real Cloudinary asset — Cloudinary's
  `server-timing` response header shows the transform actually applied
  (`width=64,height=64` vs. the source `owidth=200,oheight=200`).
- **`avatar` absent**: unchanged from the original design — synthetic hash =
  `md5(class_name).hexdigest()`, deterministic and stable forever since
  `class_name` is the immutable leaderboard key. URL:
  `https://www.gravatar.com/avatar/{synthetic_hash}?d=identicon&f=y&s={size}`.
  No Cloudinary account needed for the fallback case; Gravatar's identicon
  service remains the anonymous default. The `f=y` ("force default") param
  makes Gravatar always render the identicon rather than checking whether the
  made-up hash coincidentally belongs to a real account.

Size is `64`x`64`px — chosen after live-testing both `20px` and `64px`
against a real Cloudinary-hosted image; `64px` was clearly more legible in a
markdown table cell. Applied uniformly across all three render call sites —
no per-call-site override.

Placement is **inline** in the existing Player cell (`<img ...> The Merovingian`), not
a separate table column — a separate column would require header/separator/
row changes in every table-building function plus updates to every
`r.split("|")[1]` name assertion in `tests/test_run_season.py` (6+ call
sites), whereas inline only touches the f-string that builds the Player
cell. No column-count or header changes anywhere.

## Components

### `game/validate.py`

- `validate_avatar(value: str) -> str | None` — new, mirrors
  `validate_display_name`.
- `_ast_errors`: extend the existing `name`-attribute AST check to also look
  for an `avatar` class attribute and validate it the same way.
- `_runtime_errors`: extend the existing `name` runtime re-check to also
  re-check `avatar`.

### `game/components/leaderboard.py`

- `avatar_img_tag(class_name: str, player: dict, size: int = 64) -> str` —
  new, builds the `<img>` tag per the fallback rule above.

### `.github/scripts/register_player.py`

- On first registration, reads `getattr(player_class, "avatar", None)`,
  validates it (registration fails, same as an invalid `name`, if
  malformed), and writes `avatar` into the new leaderboard entry — key
  omitted entirely if not set.

### `.github/scripts/lb_update_player.py`

- Already re-runs on every `players/*.py` modification (via
  `update-leaderboard.yml`) to sync `display_name`. Extend it to also
  re-sync `avatar` (add, update, or remove the key based on the current
  state of the `avatar` attribute).

### `leaderboard.yaml` schema

New optional field per player entry:

```yaml
players:
  Merovingian:
    display_name: The Merovingian
    avatar: hdyiihba/The_Merovingian_200x200_rqd12y.png
    ...
```

Stores the raw identifier, not a resolved URL — the URL is built at render
time. Absent for players who haven't set one. No migration/backfill needed
for existing entries — `avatar_img_tag` already handles the absent case.

### Render call sites (3)

Each just prepends `avatar_img_tag(class_name, p)` to the existing Player
cell string — no column/header changes:

| File                            | Function                     | Consumed by                                                |
| ------------------------------- | ---------------------------- | ---------------------------------------------------------- |
| `.github/scripts/run_season.py` | `_standings_table`           | README standings + `_write_summary` (GitHub issue comment) |
| `.github/scripts/run_season.py` | `_quarter_leaderboard_table` | README unified quarter view                                |
| `game/simulation/quarter.py`    | `write_report`               | local `sim-*.md` reports                                   |

## Error / Edge Handling

- **Malformed `avatar` string** (no `/`, bad cloud-name charset, bad
  public-id charset, disallowed/missing extension): PR validation fails via
  `game.validate`, same UX as an invalid `name`.
- **`avatar` attribute removed** after being set: next sync
  (`lb_update_player.py`) removes the `avatar` key from the leaderboard
  entry, reverting that player to the synthetic-hash Gravatar fallback.
- **Two players share the same synthetic-hash fallback pattern by
  coincidence**: not possible — synthetic hash is `md5(class_name)` and
  class names are unique (the leaderboard key).
- **Player never registered / entry missing `avatar` key**: `avatar_img_tag`
  treats a missing key identically to an explicit `None`.
- **Off-domain redirection via crafted `cloud_name`/`public_id`**: not
  possible — `res.cloudinary.com` is a literal in `avatar_img_tag`, never
  derived from player data; validated player data only ever fills path
  segments after the fixed host.

## Testing (TDD)

- `validate_avatar`: valid `cloud_name/public_id.ext`, missing `/`, bad
  cloud-name charset, bad public-id charset, disallowed extension (`.svg`),
  missing extension, `..` path segment rejected, empty string rejected.
- `avatar_img_tag`: real avatar → URL is
  `res.cloudinary.com/{cloud}/image/upload/w_{size},h_{size},c_fill/{public_id_ext}`;
  missing avatar → URL uses `md5(class_name)` against Gravatar with `f=y`;
  output is deterministic across calls for the same input; `size` parameter
  reflected in both the `w_`/`h_` transform and `width`/`height` attrs;
  default size is `64`.
- `game/validate.py` AST + runtime phase tests for a player file with a
  valid `avatar`, an invalid one, and none at all (mirroring existing `name`
  test coverage).
- `register_player.py` / `lb_update_player.py`: registering a player with an
  `avatar` attribute writes it to the leaderboard; editing an existing
  player to add/change/remove `avatar` updates/removes the key on next
  sync.
- Existing `_standings_table` / `_quarter_leaderboard_table` tests in
  `tests/test_run_season.py` already tolerate an `<img>` prefix on the
  Player cell (via the `_cell_name` helper) — no further change needed
  there beyond the rename.

Run via `just pytest-all` (engine/CI scope, not `player_tests/`).

## Docs

Rewrite the `avatar` bullet in `docs/wiki/Player-Guide.md` (was `gravatar`):
explain that this requires a free Cloudinary account, and show a full
worked example so authors can see exactly which substring to copy:

```
Full delivery URL: https://res.cloudinary.com/hdyiihba/image/upload/The_Merovingian_200x200_rqd12y.png
                                               └───┬────┘             └──────────────┬───────────────┘
                                              cloud_name                      public_id.ext

avatar = "hdyiihba/The_Merovingian_200x200_rqd12y.png"
```

## Out of Scope

- No avatar rendering in the TUI (`game/tui`) — terminals can't reliably
  show remote images; explicitly excluded per discussion.
- No arbitrary avatar-URL support — `cloud_name/public_id.ext` only, by
  design (see Background).
- No backfill/default `avatar` written for existing players — the
  synthetic-hash Gravatar fallback already covers them at render time with
  no schema change needed.
- No live existence check against Cloudinary during validation — format-only,
  matching every other `validate_*` check. A typo'd `public_id` just 404s at
  render time rather than failing CI.
