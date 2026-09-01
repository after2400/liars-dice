# Hall of Shame — Design Spec

**Date:** 2026-07-08
**Status:** Draft — pending user review

---

## Overview

Some players have found ways to gain an unfair advantage that violate the spirit (and sometimes the letter) of the engine's rules — either by exploiting a gap in the runtime security model (e.g. reading hidden game state), or by tripping an existing detector (e.g. algo-tampering, forbidden syscalls). These bots are never allowed to run for real, but the fact that someone found the hole is worth a permanent, public record — both to give credit for the cleverness and to build institutional memory of what's already been tried.

This spec defines a single documentation pattern — the **Hall of Shame** — that covers every way such a bot can be discovered, without ever publishing a working exploit.

Two prior real cases motivate this: **Agent Smith** (a sabotage bot that was merged, ran a full season undetected, and was only caught and expelled after the engine's tampering-detection was added) and **The Architect** (a bot discovered locally via `just simulate-quarter`, which reads every player's dice through runtime introspection instead of playing under uncertainty — currently >95% win rate in simulation, never submitted as a PR).

---

## A. Artifact & location

A single wiki page, `docs/wiki/Hall-of-Shame.md`, with one section per bot. This repo already syncs `docs/wiki/*` to the real GitHub wiki automatically on merge to `main` via `sync-wiki.yml` — no new tooling required. The page is linked from `Home.md` alongside the existing Player-Guide and Rules pages.

No GitHub issue is required for a Hall of Shame entry itself (closing an issue doesn't delete it, but a single browsable wiki page is more discoverable than digging through `is:issue label:...`). Issues may still be opened manually for discussion of a specific entry, at the author's discretion — that's outside the scope of this pattern.

## B. Entry schema

Every entry uses the same fields, regardless of how the bot was caught:

| Field                   | Description                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Name + date/quarter** | Bot's display name and when it was found/caught                                                                                                                                                                                                                                                                                                                                                                                                                     |
| **How it was caught**   | One of: _Caught post-merge_, _Disclosed before merge_, _Caught live by engine_                                                                                                                                                                                                                                                                                                                                                                                      |
| **Result**              | Win rate, games played, tier reached. Simulation stats for pre-merge disclosures; real season/tier stats (from `leaderboard.yaml` / tournament history) for the other two                                                                                                                                                                                                                                                                                           |
| **What happened**       | Prose describing the _advantage gained_ (e.g. "saw every player's dice instead of just its own"), never the _mechanism_ used to get it. How much detail beyond that is safe is an editorial judgment made at write-up time, not a fixed rule — a bot stopped by a general, variant-proof detector (like the algo-tampering heartbeat) can usually bear more detail than one stopped by a narrow blocklist patch, since the latter may still have unpatched siblings |
| **Status**              | Patched/Blocked, with a link to the fixing PR if one exists                                                                                                                                                                                                                                                                                                                                                                                                         |

## C. Per-scenario workflow

### 1. Caught post-merge (e.g. Agent Smith)

The bot already ran for real and was later caught/expelled once a detector existed. A human writes the entry directly as a PR to `docs/wiki/Hall-of-Shame.md`. No gating — it's already-resolved history, and the fix is already live.

### 2. Disclosed before merge (e.g. The Architect)

Found via local simulation or otherwise, and deliberately never submitted as a PR. A human writes the entry directly as a PR to `docs/wiki/Hall-of-Shame.md`, but **that PR cannot land until the engine fix for this specific bot has merged** — the write-up must never describe a still-open hole. The bot's source file itself is never committed to `players/`; only the wiki entry becomes part of the repo. (`the_architect.py` currently sits untracked in the working tree and should be moved out of `players/` once documented, per this rule.)

### 3. Caught live by the engine (any future bot, no human disclosure)

`expel_player()` (`game/season/utils.py:62`) is the single shared choke point used by both `run_season.py` and `reset_season.py` when a real (non-dry-run) `SecurityViolation` fires. It already deletes the leaderboard entry _and_ the offending source file immediately, with only a stderr log line as a trace — meaning the evidence is gone before any human reviews it.

To avoid silently losing these:

- Promote `reset_season.py`'s existing `_gh_create_issue` / `_gh_post_comment` helpers (currently module-private, used for the quarterly tracking issue) into `game/season/utils.py` so both driver scripts can share them.
- Add one call, right after each existing `expel_player(...)` call site (`run_season.py:206`, `reset_season.py:151`), that files a minimal placeholder issue: bot name, date, and which detector caught it (e.g. algo-tampering vs. forbidden-syscall). Naming the detector is safe — these are already-public, variant-proof detectors documented in `game/components/security.py`, not an open hole.
- Label the issue `hall-of-shame-pending`. A human later converts it into a full wiki entry and closes the issue.
- Respects `_DRY_RUN` exactly like `expel_player()` itself — local `just simulate-*` runs never file real issues, matching existing behavior.

---

## Open items (flagged for user review)

- Exact wording/template for the wiki page header and per-entry section hasn't been drafted yet — worth a pass once the first two entries (Agent Smith, The Architect) are actually written.
- The Architect's entry is blocked on the frame-introspection engine fix landing first (tracked separately — see the sandboxing investigation).
