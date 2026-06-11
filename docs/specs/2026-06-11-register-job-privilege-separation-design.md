# Register-Job Privilege Separation — Design

**Date:** 2026-06-11
**Status:** Approved (discussed in session, design agreed before implementation)

## Problem

`register-player.yml` has two jobs:

- `validate` — unprivileged. Holds only the automatic `GITHUB_TOKEN`. Runs
  `game.validate`, which **imports the submitted player file** (executes its
  module-level code).
- `register` — privileged. Its "Validate and queue merge" step sets
  `GH_TOKEN: ${{ secrets.LEADERBOARD_PAT }}` and, in the addition path, runs
  `register_player.py`, which **also imports the submitted player file**
  (`register_player.py:70`, `spec.loader.exec_module(module)`).

The second case is the vulnerability: contributor-controlled code executes in a
process whose environment contains the `LEADERBOARD_PAT`. A malicious
`players/evil.py` with module-level code like
`os.environ["GH_TOKEN"]` can read or abuse the PAT (push to `main`, comment,
etc.).

### Severity, as scoped today

- Trigger is `pull_request` (not `pull_request_target`), so **fork** PRs receive
  no secrets — the PAT is empty for them. Exploitation requires a PR from a
  **branch in this repo**, i.e. a write-access collaborator.
- The PAT is a **fine-grained token scoped to `after2400/liars-dice` only**,
  with `Contents: read/write` and `Pull requests: read/write`, no user
  permissions. (`Workflows: write` was present and has been removed by the
  owner.) Blast radius is therefore contained to this one repo.

Net: contained, but a genuine privilege bug — the automation hands contributor
code a credential it never needs.

## Why the PAT exists (constraint we must preserve)

`update-leaderboard.yml` triggers on `push` to `main` touching `players/*.py`.
Merges performed with the built-in `GITHUB_TOKEN` do **not** trigger downstream
workflows (GitHub loop-prevention). The PAT's push _does_ re-trigger
`update-leaderboard`, which performs the real leaderboard write. So the PAT must
remain the identity that performs the squash-merge. We are not removing the PAT;
we are removing untrusted code execution from the step that holds it.

## Design

Two changes, both in `register-player.yml`, plus one tiny supporting script.

### Change 1 — Remove player-code execution from the privileged job

The privileged `register` job must never import/exec a player file. It already
gates on `needs: validate`, and the `validate` job already performs _every_
import-based check `register_player.py` did, and more:

| Check                                        | `register_player.py` | `game.validate.validate` |
| -------------------------------------------- | -------------------- | ------------------------ |
| File loads / execs without crashing          | yes                  | yes                      |
| Class matches filename (case-insensitive)    | yes                  | yes                      |
| Instantiates without crashing                | no                   | yes                      |
| `algo` is callable                           | no                   | yes                      |
| Display-name rules (`validate_display_name`) | yes                  | yes                      |

So dropping `register_player.py` from the `register` job loses no coverage. The
only thing it uniquely performed was the **uniqueness check** ("already
registered"). That does not require importing the player: the contract
guarantees the class name equals the filename stem (case-insensitive), and the
leaderboard is keyed by class name. Uniqueness is therefore a case-insensitive
key match against `leaderboard.yaml` — pure data, no code execution.

A new script `.github/scripts/lb_has_player.py <stem>` prints `true`/`false`
for that match (mirroring the existing read-only `lb_owner.py`). The addition
path calls it instead of `register_player.py`, and the temp-leaderboard copy is
deleted.

The real registration is unchanged: it still happens in `update-leaderboard.yml`
after merge, which runs `register_player.py` against the real `leaderboard.yaml`.
That job runs on `push` to `main` (post-merge, trusted content) — not on PR
content — so executing the player there is acceptable.

### Change 2 — Per-job least-privilege permissions

Today permissions are set at workflow level (`contents: write`,
`pull-requests: write`) and inherited by both jobs. This means the `validate`
job — the one that _does_ execute untrusted code — runs with a `GITHUB_TOKEN`
that `actions/checkout` persists on disk with `contents: write`. Exec'd player
code could read `.git/config` and push to `main` with it.

Move permissions to job level:

- `validate`: `contents: read`, `pull-requests: write` (reads code, comments on
  failure; cannot write contents).
- `register`: `contents: read`. It performs privileged operations with the PAT
  (`GH_TOKEN`), so its own `GITHUB_TOKEN` only needs checkout read. Rejection
  comments in this job already use the PAT, not `GITHUB_TOKEN`.

After both changes: the job that runs untrusted code holds no PAT and only a
read-scoped `GITHUB_TOKEN`; the job that holds the PAT runs no untrusted code.

## Out of scope (residual notes)

- The `register` job's `uv sync` step runs against the checked-out `pyproject.toml`.
  A PR could modify build config, but (a) the job skips any PR touching
  non-`players/` files, and (b) no secret is present in the `uv sync` step's env
  (step-scoped). Low risk; not addressed here.
- `register_player.py` itself is unchanged — it remains the registration logic
  used by `update-leaderboard.yml` on trusted, post-merge content.

## Testing

- Unit test `lb_has_player.py` (subprocess against a temp `leaderboard.yaml`),
  mirroring `tests/test_register_player.py`: present (case-insensitive) → `true`;
  absent → `false`; empty/missing file → `false`.
- Full suite stays green (`uv run pytest`).
- Workflow YAML: there is no `actionlint` in this environment; verify the file
  parses as YAML and review the diff by hand. Final end-to-end confirmation is a
  throwaway player PR (owner-run) after merge.
