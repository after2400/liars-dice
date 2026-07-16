# CHANGELOG


## v3.0.0 (2026-07-16)

### ✨ Features

- Remove v1 algo() interface (hard cutover to v2)
  ([`635118f`](https://github.com/after2400/liars-dice/commit/635118fa8bf6ac162bb0cf480dd8dcca58798e00))

game_orchestrator no longer inspects each player's algo() signature to decide how to call it — it always builds a GameContext and calls algo(ctx). game.validate now hard-rejects any non-(self, ctx) signature instead of warning and falling back to the v1 call path.

Rebasing onto security/player-isolation (#201) surfaced a second, independent v1/v2 dispatch inside the isolated worker (game/components/isolation/worker.py's worker_main), plus a stub `.algo` in game/components/utils.py's roster loader whose signature was deliberately shaped to match whatever a real player declared. Without also simplifying those, a v1-signature bot registered locally without validation (game.validate is opt-in for local registration) would still run correctly through the isolated-worker path — the cutover wouldn't actually be hard everywhere. Both are now v2-only: worker.py always builds a GameContext, and the roster-loading stub is a fixed `algo(self, ctx)` shape.

Updated CONTRIBUTING.md and the Player Guide to drop the v1 migration section, and removed/updated the tests and example fixtures that exercised the now-deleted v1 dispatch paths.

Closes #106.

### Breaking Changes

- Player bots must define algo(self, ctx). The v1 positional-arg signature (hand, prior_bet,
  total_dice, bet_history, outcomes, stats=None, tier=None, round_players=None) is no longer
  accepted anywhere, on any execution path.


## v2.8.0 (2026-07-16)

### 🛡️ Security

- **security** · feat: Add fixed-shape result wire protocol for isolated workers
  ([`481b7f4`](https://github.com/after2400/liars-dice/commit/481b7f467eda0a376cb83b2bc96c81957af52f5a))

Encodes per-turn results (Bet, liar call, or worker error) as struct-packed 5-byte messages over the control pipe. Decoding sets player field to None, allowing the parent process to fill in the known acting player identity.

- **security** · feat: Add isolated player worker bootstrap and turn loop
  ([`e18bec8`](https://github.com/after2400/liars-dice/commit/e18bec80a347db60c06425b75642687ebb10fae3))

Adds worker.py, the multiprocessing child entry point that scrubs secrets, restricts cwd, seeds RNG, and loads/instantiates the player under enforce() before entering the recv/algo/send turn loop. Loads by absolute file path (not module name) since real players aren't importable by name in a fresh spawn interpreter. Read-model args (bet_history/outcomes/stats) are stubbed empty until the shared arena lands in a later task.

- **security** · feat: Add read-only shared-memory read-model for isolated workers
  ([`db88ea2`](https://github.com/after2400/liars-dice/commit/db88ea29ae929dfa9789890b235ddbc99f6f9936))

Isolated player workers can now see the game's bet history and round outcomes without marshalling growing state across the process boundary each turn. A ReadModelWriter in the parent appends fixed-field bet records and length-prefixed pickled outcome blobs into a multiprocessing.shared_memory block; ReadModelReader in each worker maps that block through a re-opened read-only mmap (spike-confirmed: memoryview.toreadonly() alone doesn't stop writes through the underlying shm.buf handle, so it isn't a real boundary) and answers bet_history_view(log_len)/outcomes_view() with direct O(1) offset reads, no scan or copy of prior entries.

WorkerConfig gains readmodel_name (default None) so existing positional construction call sites keep working untouched. worker.py opens the reader once at startup and wires it into GameContext per turn.

- **security** · feat: Add worker environment scrubbing for player isolation
  ([`088ae49`](https://github.com/after2400/liars-dice/commit/088ae49c77e04ef83f128c15c0c8add5b91ae1b2))

- **security** · feat: Add WorkerPool with forced-kill timeout and respawn
  ([`b772663`](https://github.com/after2400/liars-dice/commit/b772663dfd3e44b5bf8bf464ed1734cfcd5c507a))

Spawns one worker process per player, calls with a wall-clock timeout, and kills+respawns on timeout or death so one bot can't wedge the pool.

- **security** · feat: Deterministic per-worker RNG seed derivation
  ([`0aba08e`](https://github.com/after2400/liars-dice/commit/0aba08ef53c047ef08f2b7b302472ac372def30a))

- **security** · feat: Isolated executor path in game_orchestrator
  ([`0d792b2`](https://github.com/after2400/liars-dice/commit/0d792b2f8f6a5dd2703bd18fd9f7ee468defa1b9))

Wire WorkerPool + ReadModelWriter into game_orchestrator's turn loop: when pool is provided, each turn is dispatched to an isolated worker via pool.call() instead of calling player.algo() in-process, with bet_history/ outcomes/stats mirrored into shared memory beforehand. Worker index is looked up by player name via a stable pool.name_to_index mapping (added to WorkerPool), not by players-list position, since game_orchestrator shuffles that list in place and run_series reuses the same list object across every game in a series.

- **security** · feat: Publish GameStats snapshot to isolated workers
  ([`d564c89`](https://github.com/after2400/liars-dice/commit/d564c89b2b42717ce31a8c96b45d40f087cd511d))

Extends the Task 6 shared-memory read-model with a double-buffered GameStats channel so isolated player workers get read-only per-turn stats without marshalling ~40 backing dicts on every turn.

GameStats.snapshot_state()/restore_state() flatten the defaultdict backing stores to plain dicts (required for pickling across spawn, since the nested defaultdict lambda factories aren't picklable). ReadModelWriter.publish_stats() writes into the currently-inactive of two buffers and flips a single header field last, so a worker mid-read of the prior snapshot is never handed a torn write. worker.py wires stats_view() into v2 bots always and v1 bots when "stats" is in their algo() signature, mirroring script.py.

- **security** · feat: Run_series drives players through isolated worker pool
  ([`82560bb`](https://github.com/after2400/liars-dice/commit/82560bb98e14d8b64017df5e11de384145b57530))

Task 10: run_series builds one WorkerPool + ReadModelWriter for the whole series (not per game), passes them to every game_orchestrator call, and tears them down in a finally block. Adds import_player_specs_from_dir (game/components/utils.py) which tags each loaded player instance with a PlayerSpec (abs file path + class name) so run_series can recover the info needed to build a WorkerConfig without changing any of the loader's existing 7 call sites; import_player_classes_from_dir is now a thin wrapper over it.

Two owner-approved scope reductions from the task brief (2026-07-14):
- isolated: bool = True kept as specified, but per-game worker reseeding is
  NOT implemented — each worker's global random is seeded ONCE per series
  instead of once per game, since re-seeding would require extending the
  parent<->worker pipe protocol (worker.py/pool.py untouched). Only affects
  bots reading the bare `random` module directly; dice/bet_history/outcomes/
  stats keep Task 9's byte-for-byte in-process/isolated parity.

ReadModelWriter sizing scales with both n_games and player count (fit from measured record counts/sizes against the real players/ directory at 4/12/27 players) after game/__main__.py's CLI tests (which pull in the whole unregistered roster, not just tier-capped pools) overflowed a games-only formula. Also fixes 23 pre-existing tests (test_main.py, test_replay_engine.py) that construct player stubs directly rather than through the loader — these now opt out via isolated=False, since two of them asserted on class-level counters mutated inside algo() that correctly no longer propagate once algo() runs in a subprocess.

- **security** · feat: Validate.py gate runs candidate in an isolated probe worker
  ([`9b533a4`](https://github.com/after2400/liars-dice/commit/9b533a4e272ef3e9a98feb5a9c75fd2b20119fd1))

Phase 2 of the CI registration gate (game/validate.py, invoked from register_player.py) used to import the candidate module and instantiate its class in-process, in the validator's own Python process, guarded only by a 10s SIGALRM. That's the exact "unguarded __init__ window" the security/player-isolation branch closes everywhere else in the runtime path.

_runtime_errors now spawns a single-worker WorkerPool and reuses worker_main (already scrubs env, chdirs to an ephemeral dir, applies enforce(), imports by file path, instantiates) to do instantiation, with WorkerPool's real process kill() replacing SIGALRM (which can't interrupt a blocking native/C-level call). It then runs one unconditional probe algo() call with an empty-history turn -- previously this only happened for bots that declared a `tier` parameter, so a bug in algo() for any other bot was never actually exercised during validation. This is a deliberate strengthening.

class-name/v1-vs-v2 detection moves from live introspection to a second, independent AST parse (_find_class_and_algo_args) -- Phase 2 no longer has a module imported in this process to inspect.

Deliberate, accepted UX regression: a worker that crashes/hangs during import, instantiation, or the probe call now surfaces only as an opaque "crashed or timed out" message, instead of the old differentiated import-vs-instantiation-vs-timeout text. The real traceback still reaches the CI log via the worker process's own inherited stderr. Updated test_tier_none_crash_fails_validation's assertion accordingly.

Bootstrap-handshake extension (worker.py/pool.py): the "ready" message becomes ("ready", name, avatar) instead of a bare string, captured from the instance before its .name is overwritten by the caller-supplied placeholder. This lets validate.py's Phase 2 -- which no longer has a live instance to read .name/.avatar off of directly -- keep validating dynamically-computed values as a fallback for the non-literal case Phase 1's AST check can't cover, rather than silently dropping that check. Purely additive: the per-turn send/recv_bytes protocol is unchanged, and no existing test asserted on the literal "ready" string. tests/test_isolation_worker.py, tests/test_isolation_pool.py, and tests/test_isolation_confinement.py all still pass.

- **security** · fix: Close child pipe end and bound worker ready handshake
  ([`67703ab`](https://github.com/after2400/liars-dice/commit/67703ab35db2fb2cc66ae80c1c39e4d77b8fadc5))

Prevents a pool hang when a bot crashes/hangs during bootstrap: closes the parent's child_conn copy for EOF detection, bounds the ready handshake with timeout_s, marks unready workers so call() degrades to WORKER_ERROR, and catches struct.error on malformed result frames.

- **security** · fix: Remove unguarded parent-process exec of player classes in run_season.py
  ([`0d6b8aa`](https://github.com/after2400/liars-dice/commit/0d6b8aafea1e6a71f0d3daedabc1022d0769987f))

_scan_v1_players imported and instantiated every registered player's real class directly in this process to inspect its algo() signature, unguarded by enforce() or scrub_environment -- the same parent-process secret-exposure hole closed in game/components/utils.py, but in the actual daily production driver where GH_TOKEN is a real job-level env var. With the last v1-signature bots migrating to v2, this scan (and its "migrate to v2" summary banner) has no remaining purpose, so removing it closes the hole rather than patching it.

- **security** · fix: Stop running untrusted __init__ unscrubbed in the parent loader
  ([`e2eb020`](https://github.com/after2400/liars-dice/commit/e2eb0208b5973497098a1a2180685bd4419dc46b))

import_player_specs_from_dir previously imported and instantiated every player's real class directly in the parent process, guarded only by enforce()'s syscall audit hook, never by env scrubbing. On every real season/tournament/quarter run this left the real GH_TOKEN/LEADERBOARD_PAT in os.environ, readable by a bot's untrusted module-level code and __init__, before any worker isolation ever kicked in.

Mirrors validate.py's existing pattern (Task 11): get the class name and algo() arg shape via pure AST parsing (no execution), get name/avatar via a one-shot isolated worker bootstrap probe, and build a lightweight synthetic shell instance in the parent — the real class is never imported or instantiated outside the scrubbed worker.

Same-process scrub-then-restore was considered and rejected: enforce() does not block thread creation, so a malicious __init__ could spawn a background thread that waits past the restore point and reads the secret later.

Updates tests/test_main.py, tests/test_security.py, and tests/test_isolation_series_parity.py, whose in-process (isolated=False) legs relied on the loader returning real, executable player instances — now bypasses the loader via plain importlib for those trusted test fixtures, since that combination is no longer supported by design.

- **security** · fix: Support slicing on isolated bet_history/outcomes views
  ([`3cc662f`](https://github.com/after2400/liars-dice/commit/3cc662f4f09345cbb41e8092ecaa952dbf60448d))

_BetHistoryView.__getitem__ and _OutcomesView.__getitem__ only handled int indices, raising TypeError on any slice. Four real PRM-tier bots (deepthought.py, ripley.py, evilstewie.py, merovingian.py) use the history[self._history_seen :] open-ended-slice idiom on ctx.bet_history, so under isolation they hit the engine's except-Exception penalty path on every turn -- confirmed as 0 wins across 1000 games in a real simulate-season run.

Add an isinstance(idx, slice) branch to both methods, resolving via idx.indices(self._n) and returning a list of already-immutable _entry_at(i) entries -- stricter than, not a regression from, _ReadOnlySequence's unwrapped slice behavior in the in-process path.

- **security** · testing: Confinement and forced-kill regression tests for isolation
  ([`166bd25`](https://github.com/after2400/liars-dice/commit/166bd25fb261aff73d030d23d8601981b97f934f))

- **security** · testing: Decouple v1-signature shell test from real player files
  ([`e8595b7`](https://github.com/after2400/liars-dice/commit/e8595b744c2ad80e1c0f734b1fc1c321211f49da))

rick.py (this test's real-bot example) migrated to the v2 interface, so the test now builds a throwaway v1-signature fixture bot instead of depending on which currently-registered player happens to still be v1 --
none are, after the rick/alice/bruno/cleo/diego migrations.

- **security** · refactoring: Skip algo-tampering heartbeat on the isolated execution path
  ([`b6b94f7`](https://github.com/after2400/liars-dice/commit/b6b94f7ff24ebbdcffc2f072048c764d60faa95d))

### 📖 Documentation

- Document just validate-player/add-player recipes
  ([`3f4440e`](https://github.com/after2400/liars-dice/commit/3f4440e14851d28e0b94497e0185abc4a2ead923))

register-player skips the game.validate CI gate entirely; the validate-player and add-player recipes (added 2026-07-12) were never documented, so both CONTRIBUTING.md and the Player Guide only showed the ungated path.

### 🏗 Chores

- **config**: Gitignore docs/players/ for local-only player and security docs
  ([`87237be`](https://github.com/after2400/liars-dice/commit/87237be0e1c3d346ac344c7739da098572b554db))


## v2.7.6 (2026-07-13)

### 🛡️ Security

- **security** · fix: Close sandbox-escape and dice-RNG leak vectors for player bots
  ([`176a4db`](https://github.com/after2400/liars-dice/commit/176a4dbea0146f49fc053e2678685378dbf25050))

Three previously-undiscovered avenues, each verified by a regression test added here (all five failed before this change):

- Whitelisting `logging` transitively exposed `logging.os` (env/secret read) and
  `import logging.handlers` (SocketHandler/HTTPHandler outbound network), both of
  which passed the AST validator cleanly. validate.py now allows only top-level
  stdlib imports and refuses attribute reach into interpreter internals and
  re-exported dangerous modules via a blocked-attribute set.
- The Architect's call-frame introspection (reading every player's dice from the
  orchestrator frame) needs no import at all — an exception __traceback__ or a
  generator gi_frame reaches it — so the import whitelist could never stop it.
  The blocked-attribute set rejects f_back/f_locals/__traceback__/_getframe/etc.
- game_orchestrator seeded the global `random` module with the same seed as the
  private dice RNG, letting a bot clone random.getstate() and predict every roll.
  The global module is now seeded from a one-way derivation instead: bots using
  bare random.* stay fully reproducible under replay, the dice RNG does not leak.

Also widen the audit-hook guard to cover player import/instantiation (the once-per-run window a hostile __init__ would use to exfil), make hook install idempotent, and fix a latent importlib.util import on the same load path.

Interim defense-in-depth; durable subprocess isolation of untrusted execution is tracked separately.

### 🔁 Continuous Integration

- **workflows**: Pin python-semantic-release to 10.6.1
  ([`e380da6`](https://github.com/after2400/liars-dice/commit/e380da62726f5828e035240e0722c0b1f94d9e75))

The vendored .semrel changelog templates are validated against 10.6.1; an unpinned upgrade could change PSR's template context and silently break the custom Security section. Pin so template and engine versions stay in lockstep.

### 📖 Documentation

- **config**: Give each player recipe a one-line description shown by 'just'
  ([`5ceaca3`](https://github.com/after2400/liars-dice/commit/5ceaca3bbb6d400201ebba2740decb9e39677dbd))

Bare 'just' runs 'just --list', which renders only the single comment line directly above a recipe. State each recipe's purpose plus a Usage: example on that one line.

### 🏗 Chores

- **config**: Add validate-player and add-player recipes
  ([`e1f7609`](https://github.com/after2400/liars-dice/commit/e1f7609112c3047b03a93c96a50807ddc477643b))

validate-player runs the exact game.validate the registration CI runs, so a contributor can confirm a bot will be accepted before opening a PR. add-player chains validate-player + register-player, registering locally only if validation passes.

- **config**: Custom emoji changelog with hoisted security section
  ([`c20c56e`](https://github.com/after2400/liars-dice/commit/c20c56e2c1eae06f05e7d53af8dbcdd0b72d5aa8))

Customizes the vendored .semrel templates:
- Prefix each type section header with an emoji and apply an explicit section
  order (macros.md.j2 gains only sort_tuples_by_order_dict; the corporate Jira
  helpers from the source template are intentionally omitted).
- Hoist every commit scoped 'security' (any type) into a single '### Security'
  section rendered first, and exclude those commits from their normal type
  section so they are not listed twice. Catches both fix(security) and feat(security) while the type still drives the version bump.
- Expand multi-line commit bodies (squash-merge friendly) via a shared
  format_body_without_footers macro that drops trailing co-author/sign-off/
  generated-with trailers, and harden the emoji lookup with .get() so an
  unlisted type can never KeyError a release.

Also registers the 'security' commit scope in .commitlintrc.mjs.

- **config**: Order the security changelog section by bump severity
  ([`2e94e11`](https://github.com/after2400/liars-dice/commit/2e94e116a7ee93c410bc42e8669d12f5830baa86))

Within the hoisted 🛡️ Security section every entry shares the 'security' scope, so the commit type is otherwise invisible. Tag each entry with an inline type label (**security** · fix:, · feat:, etc.) and order the section by bump severity (breaking > feat > fix/perf > other), then alphabetically within a rank, so the most impactful change reads first.

- **config**: Vendor stock PSR markdown changelog templates into .semrel
  ([`1c19fdb`](https://github.com/after2400/liars-dice/commit/1c19fdb616946572c9da224a05634b77588dbb36))

Activates template_dir = ".semrel" (already set in pyproject.toml but pointing at a missing dir, so PSR was using its built-ins). Byte-identical to the stock python-semantic-release conventional/md template set — verified the same across 10.2.0 and 10.6.1, so it is a safe base. The security CHANGELOG-section customization lands in the next commit.


## v2.7.5 (2026-07-08)

### 🐞 Bug Fixes

- **engine**: Render Player Performance table as markdown, not fixed-width text
  ([#191](https://github.com/after2400/liars-dice/pull/191),
  [`6559dfd`](https://github.com/after2400/liars-dice/commit/6559dfde40e229525edbf18bf09f336d2be13a19))

## Summary

`format_perf()` in `game/components/series.py` printed the Player Performance table as fixed-width ASCII text. That only stays aligned in a monospace/`pre` context — `quarter.py`'s `_format_output()` code-fences `=== Series Results` blocks (the win-rate chart) but never recognized `=== Player Performance` blocks, so the perf table fell through as plain text. Its column padding collapsed to single spaces when `sim-*.md` was rendered by a markdown viewer, making the table unreadable.

`format_perf()` now emits GFM pipe-table syntax instead, still column-padded so it also reads cleanly as raw, unrendered text. No changes needed to `_format_output()` — its default branch already preserves blank lines and passes table rows through untouched.

## Test plan

- [x] `just pytest tests/test_perf.py` — 19 passed (assertions are substring-based, unaffected by the format change)
- [x] `just pytest-all` — 400 passed
- [x] Ran `simulate-quarter --profile-memory` against a scratch copy of `leaderboard.yaml` and confirmed the generated `sim-*.md` contains valid GFM tables with correctly rendered columns, including the memory-profiling columns


## v2.7.4 (2026-07-06)

### 🐞 Bug Fixes

- **engine**: Wire README updates into tournament reset; fix expulsion chmod-timing bug
  ([#190](https://github.com/after2400/liars-dice/pull/190),
  [`331ec66`](https://github.com/after2400/liars-dice/commit/331ec66156279dacbacbeea06673185bcf676f27))

## Summary

Started as a one-off README data refresh, but uncovered a real structural gap plus a second serious bug while wiring the permanent fix:

1. **`reset_season.py` never called `_update_readme()` at all** — only `run_season.py`'s regular Monday flow did. This is why the corrupted tournament left README.md showing Agent Smith's fraudulent 100% win rate until manually patched in the first commit of this PR. Every future tournament would have hit the same stale-README gap for up to a week. 2. **A second, more serious bug found while fixing #1**: both of `run_season.py`'s tier-running branches (L1 pools and regular tiers) `chmod` `lb_path` read-only (`0o444`) for the duration of the game-running call — the exact same pattern `reset_season.py`'s `run_pools()` has, which #187 already handled correctly there. But `_run_tier`/`_run_players` still called `expel_player()` **internally**, i.e. while `lb_path` was still locked — meaning a real security violation in a regular Monday tier run would crash with an uncaught `PermissionError`. This is also what I misdiagnosed as a "sandbox artifact" earlier in this session when testing `run_season.py` directly — it wasn't a sandbox issue, it was this.

## Fix

- Moved `_update_readme`/`_standings_table`/`_quarter_leaderboard_table` (plus their constants) from `run_season.py` into `game.season.utils`, alongside `expel_player` and `run_game_with_retry`, so both scripts share one implementation. `reset_season.py`'s `main()` now calls it right after `create_season_issue()`, mirroring `run_season.py`.
- `_run_tier`/`_run_players` now return `(wins, offenders)` instead of expelling internally; `run_season()` expels each offender only after its `chmod(0o644)` restore — matching `reset_season.py`'s existing (correct) pattern exactly.

## Test plan

- [x] `just pytest-all` — 400 passed
- [x] `just lint` — clean
- [x] Verified locally: corrupted README.md with a marker, ran `reset_season.py` end-to-end in an isolated scratch copy, confirmed the marker was replaced with fresh standings and `[done] README standings updated.` was printed.

### 🏗 Chores

- **leaderboard**: Reset Q3 tournament_state for a clean re-run
  ([#188](https://github.com/after2400/liars-dice/pull/188),
  [`ffdc712`](https://github.com/after2400/liars-dice/commit/ffdc712854f1bed3b7c082a9f7730d3b1d898c17))

## Summary

The tournament that ran before #187's fix landed had `agent_smith`'s pool (7 players) return `{}` entirely once the security violation crashed it — six innocent players got zero real games and silently kept their pre-tournament tier instead of a fresh placement.

Clearing `quarter`, `pool_results`, and `issue_created` from `tournament_state` lets `reset_season.py` treat this as a fresh run, so every player gets real games this time — now that a violation retries the pool excluding the offender instead of discarding it (#187).

Issue #186 (created by the corrupted run) is being deleted separately; a fresh tracking issue will be created by the clean re-run.

## Test plan

- [x] Diff is surgical — only `tournament_state` removed, nothing else touched
- [ ] Once merged: delete issue #186, re-trigger `force_tournament=true`, verify all 27 players get real placements


## v2.7.3 (2026-07-06)

### 🐞 Bug Fixes

- **engine**: Retry a tier/pool excluding the offender instead of discarding it
  ([#187](https://github.com/after2400/liars-dice/pull/187),
  [`440eceb`](https://github.com/after2400/liars-dice/commit/440eceb7dda04161221462b45b07cf397396c0a4))

## Summary

Discovered after the Q3 tournament ([Actions run 28820959685](https://github.com/after2400/liars-dice/actions/runs/28820959685)): when a security violation was caught, `_run_tier`/`_run_players`/`_run_pool` discarded the **whole batch's** results, not just the offender's. In the real tournament run, `agent_smith`'s pool (`Stewie`, `agent_smith`, `Diego`, `Shwimpevwild`, `Alice`, `Nuke`, `Rick`) returned `{}` entirely — **six innocent players got zero real games**. Since `assign_placements()` only writes a tier for names present in the (now incomplete) win-ranking, those six kept whatever tier they had *before* the tournament ran, silently misrepresented in the tournament summary as a fresh result.

## Fix

- Added `--exclude` to `game/__main__.py`'s player selection (works with both `--tier` and `--players`).
- Added a shared `run_game_with_retry()` in `game.season.utils`: run once, and if a security violation is detected, retry a single time with `--exclude <offender>` so the rest of the tier/pool gets real games. Only gives up (returns `{}`) if the retry itself also hits a violation or an ordinary crash.
- `_run_tier` and `_run_players` (`run_season.py`) and `_run_pool` (`reset_season.py`) are now thin wrappers around `run_game_with_retry`, replacing three near-identical copies of the same subprocess/retry logic.
- Expulsion timing is unchanged — `reset_season.py`'s `run_pools()` still collects offenders during its `chmod(0o444)`-protected loop and expels them only after write access is restored.

## Test plan

- [x] `just pytest-all` — 399 passed
- [x] `just lint` — clean
- [x] **Verified locally end-to-end with the real `players/agent_smith.py` bot** (pulled from git history, since it's since been deleted from `main`) against an isolated scratch copy of the repo: confirmed the violation is detected, the pool retries and the other six players get real recorded wins instead of `{}`, Smith is expelled (leaderboard entry + file both removed), and `assign_placements` correctly places all 27 remaining players from real results with no stale/missing tiers.
- [ ] Once merged: reset `tournament_state` in the real `leaderboard.yaml`, delete issue #186, and re-trigger a clean full Q3 tournament re-run so every player gets a fair, fresh placement this quarter.


## v2.7.2 (2026-07-06)

### 🐞 Bug Fixes

- **scripts**: Wire tournament pools into expulsion; fix gh issue create
  ([#185](https://github.com/after2400/liars-dice/pull/185),
  [`ae5a42e`](https://github.com/after2400/liars-dice/commit/ae5a42ed7da881d2c87d70817b241b53d38b7c2f))

## Summary

Today's forced tournament run ([28818918047](https://github.com/after2400/liars-dice/actions/runs/28818918047)) surfaced two separate, real bugs on top of #184's fixes:

1. **`gh issue create` doesn't support `--json`** (that flag only exists on read commands like `gh issue list`). It prints the created issue's URL to stdout on success, not JSON — `_gh_create_issue`'s `json.loads(result.stdout)["number"]` always failed once this code path actually ran for real. Fixed to parse the issue number from the URL. 2. **`agent_smith` was correctly detected during tournament pool play** (`SECURITY_VIOLATION:agent_smith`, exit 127) — but `reset_season.py`'s `_run_pool` had zero integration with expulsion. It just logged a generic `[warn] pool game engine exited 127` and returned `{}`, so Smith proceeded straight into `assign_placements()` and landed in **Premier tier**, completely unstopped, in exactly the event that determines dominance for the quarter. Only `run_season.py` (the regular Monday driver) got expulsion wiring in #184 — `reset_season.py` (the quarterly driver) never had it.

## Approach

To avoid duplicating expulsion logic, `_expel_player` is promoted from a `run_season.py`-local function to `game.season.utils.expel_player(lb_path, class_name, repo_root, dry_run)`, taking its dependencies as explicit parameters instead of module globals. Both scripts now import and call the same implementation.

One wrinkle: `reset_season.py`'s `run_pools()` chmods `leaderboard.yaml` read-only (`0o444`) for the duration of the pool loop, as a defense against a pool game writing to it directly. So `_run_pool` now returns `(wins, offender)`, offenders are collected during the loop, and expulsion happens only *after* `run_pools()` restores write access and finishes its own leaderboard save — doing it inline would either hit a `PermissionError` (file still read-only) or have its write clobbered by `run_pools()`'s own subsequent save of stale in-memory data.

## Test plan

- [x] `just pytest-all` — 394 passed
- [x] `just lint` — clean
- [x] Moved the `expel_player` unit tests to `tests/test_season_utils.py` (where the shared implementation now lives); added `test_run_pools_expels_security_violation_offender` and `gh issue create` URL-parsing coverage in `tests/test_reset_season.py`
- [ ] Re-run the forced tournament (`workflow_dispatch` with `force_tournament: true`) once merged, to confirm Smith is actually expelled before placement and the issue gets created successfully


## v2.7.1 (2026-07-06)

### 🐞 Bug Fixes

- **engine**: Repair broken security hardening that crashed today's tournament
  ([#184](https://github.com/after2400/liars-dice/pull/184),
  [`bed1d29`](https://github.com/after2400/liars-dice/commit/bed1d29bd6797ad26b9f8d31e7678b123ea4c018))

## Summary

PR #182's security hardening ("The Fortress") was broken at nearly every layer, and it's why today's real Q3 tournament run (#28792210977) crashed mid-PRM-tier with an uncaught `ImportError`.

- **`PlayerProxy` broke player identity everywhere.** Wrapping every player made `type(p).__name__` return `"PlayerProxy"` for all of them, colliding results/stats/replay keys across the whole engine — 39 tests were failing on `main` before this PR.
- **The audit hook never escalated to expulsion.** It raised plain `RuntimeError`, which `game_orchestrator` treated as an ordinary bot crash rather than a security event.
- **Expulsion could never match anyone.** It matched offenders by
*display name* ("Agent Smith") against a leaderboard keyed by *class name* (`agent_smith`) — a silent no-op every time.
- **`_expel_player` imported from the wrong module** (`game.components.leaderboard` instead of `game.season.utils`) — the literal `ImportError` that crashed today's run.
- **Dead code**: `freeze_module` never actually intercepted anything and was never called.
- **Two more bugs surfaced while fixing the above**: 3 of the 6 "forbidden syscalls" (`os.write`, `os.setuid`, `os.setgid`) aren't real CPython audit events and never fired (verified empirically); and the audit hook — process-global and permanent by design — was leaking into legitimate `subprocess` use elsewhere in the same process (e.g. `validate_player.py`'s sandboxing), breaking unrelated tests.
- **`_expel_player` could delete real repo files as a side effect of tests/local sims.** Now guarded so destructive action only fires against the actual live `leaderboard.yaml`.
- **The CI guard step was itself dangerous**: it `exec`'d the *entire* `reset_season.py` just to read a boolean, actually running the real tournament reset as a side effect, and silently falling back to `mode=season` on any failure — the actual reason today's Q3 tournament never started. Replaced with a pure date check.
- Removed ad-hoc debug files committed to the repo root (`test_security.py`, `test_smith_violation.py`, `test_lb.yaml`, `season_summary.md`) and added real coverage in `tests/test_security.py` and `tests/test_run_season.py`.

Full root-cause writeup is in the commit message.

## Test plan

- [x] `just pytest-all` — 390 passed
- [x] `just lint` — clean
- [x] End-to-end verification in an isolated repo copy: `agent_smith` correctly detected, attributed by class name, and routed into the real expulsion path against a live leaderboard
- [ ] Re-trigger the Q3 tournament reset once this merges (`workflow_dispatch` with `force_tournament: true`, or wait for the guard step's fixed date check on the next scheduled run)


## v2.7.0 (2026-07-06)

### 🛡️ Security

- **security** · feat: Implement runtime hardening and automated expulsion system
  ([#182](https://github.com/after2400/liars-dice/pull/182),
  [`df799f6`](https://github.com/after2400/liars-dice/commit/df799f67c6e10cc88f6c8c5fecfa13f53c3a7c8f))

Implements a multi-layered security architecture ("The Fortress") to protect the league from malicious bots that attempt state hijacking or opponent sabotage.

### Key Components
- **Runtime Hardening**: Implements Python audit hooks via `game/components/security.py` to block forbidden syscalls (e.g., `os.write`, `socket.connect`).
- **Integrity Heartbeats**: Introduces a `PlayerProxy` and periodic snapshot checks in `game/components/script.py` to detect if a player's `.algo` method has been monkey-patched or modified during a game session.
- **Automated Expulsion**: Updates the CI driver (`.github/scripts/run_season.py`) to monitor for exit code `127`. Upon detection of a `SecurityViolation`, the offending bot is automatically removed from `leaderboard.yaml` and its source files are deleted from the repository.
- **Exception Hierarchy**: Defines `SecurityViolation` in `game/components/exceptions.py` to distinguish security breaches from standard runtime errors.

Verified via `test_smith_violation.py`.


## v2.6.0 (2026-07-02)

### ✨ Features

- **game**: Player performance instrumentation (wall/CPU/memory)
  ([#173](https://github.com/after2400/liars-dice/pull/173),
  [`6ce352b`](https://github.com/after2400/liars-dice/commit/6ce352bb571fb85cf079f9e8d08da9e6759d9d36))

## Summary
- Adds `PerfTracker` (`game/components/perf.py`) to record per-player wall-clock and CPU time (always on) and optional peak memory per `algo()` call (`--profile-memory`, tracemalloc-based), surfaced as a `Player Performance` table in `simulate-season`/`simulate-tournament`/`simulate-quarter` output. Phase 1 only — ephemeral, local-simulation-only, no `leaderboard.yaml` schema changes, no production CI wiring.
- Documents `--profile-memory` and how to read the perf table for player authors in `CLAUDE.md`'s Local simulation section.
- Three small unrelated TUI fixes bundled in for convenience during testing: widen the standings name column to fit the longest player name, make the log panel focusable/copyable (mirrors the existing per-player panel copy pattern), and fix a stale test that collided with the real `Oracle` bot class.

## Test plan
- [x] `just pytest-all` — 385 passed
- [x] Verified squash preserved identical content vs. the original 14-commit history (diffed old tip vs. new tip scoped to changed files)
- [x] Manually confirmed the memory-baseline fix and log-panel-copy fix against a live 13-week quarter simulation

Relates to #172 (implements the copy-to-clipboard follow-up discussed there; the tier-panel misrouting bug itself is not fixed by this PR).

---------

Co-authored-by: Claude Sonnet 5 <noreply@anthropic.com>


## v2.5.1 (2026-07-02)

### 🐞 Bug Fixes

- **workflows**: Share one concurrency group across leaderboard writers
  ([#170](https://github.com/after2400/liars-dice/pull/170),
  [`15b3130`](https://github.com/after2400/liars-dice/commit/15b3130af09294af3d3a096ca7e140fab0a4534f))

## Summary
- `run-season.yml` and `update-leaderboard.yml` each had their own `concurrency` group, guarding only against overlapping with themselves — nothing stopped the two different workflows from racing each other while both read-modify-write `leaderboard.yaml`/`README.md`
- This raced for real after merging #156 (add HAL 9000): the "new player" step in `update-leaderboard.yml` dispatched an out-of-band `run-season.yml` run, which collided with a concurrent `update-leaderboard.yml` commit landing in the same window. The `git pull --rebase` hit a merge conflict and failed, discarding HAL's computed game results — see #169
- Fix: both workflows now share `concurrency: { group: leaderboard-write }`, so any job touching `leaderboard.yaml` serializes behind any other, regardless of which workflow triggered it

Closes #169

## Test plan
- [x] `just pytest-all` — 353/354 pass (1 pre-existing failure in `test_tui.py`, unrelated, also fails on `main`)
- [x] Validated both workflow YAML files parse correctly with `yq`

## Follow-up Once merged, manually re-dispatch `run-season.yml` to give HAL his first season games now that the race is fixed.

Co-authored-by: Claude Sonnet 5 <noreply@anthropic.com>


## v2.5.0 (2026-07-01)

### ✨ Features

- Add optional Cloudinary avatars for players
  ([#157](https://github.com/after2400/liars-dice/pull/157),
  [`1195eb5`](https://github.com/after2400/liars-dice/commit/1195eb5d5a67349ec4655f4763dd12600818c131))

## Summary
- Adds an optional `avatar` class attribute to player bots (`cloud_name/public_id.ext`), validated in both the AST and runtime phases alongside the existing `name` checks
- `avatar_img_tag` renders a 64x64 Cloudinary-hosted image when set, falling back to a deterministic Gravatar identicon (keyed on class name) when absent, so tables stay visually uniform
- `register_player.py` and the renamed `lb_update_player.py` (was `lb_update_name.py`) sync `avatar` into `leaderboard.yaml` on registration and on every subsequent edit — same CI path already used for `display_name`, no new workflow needed
- Rendered in README standings, the season summary, and local `sim-*.md` quarter reports

Design doc: `docs/specs/2026-07-01-player-avatars-design.md`. This supersedes an earlier Gravatar-specific design (Gravatar only allows one avatar per email account, which doesn't work for an author with multiple bots).

## Test plan
- [x] `just pytest-all` — 353/354 pass (1 pre-existing failure in `test_tui.py`, unrelated to this change, also fails on `main`)
- [x] Verified `avatar_img_tag` renders real Cloudinary URLs end-to-end against a live asset, and Gravatar-identicon fallback when `avatar` is absent
- [x] Verified `lb_update_player.py` correctly syncs `avatar` into `leaderboard.yaml` on player-file edits

---------

Co-authored-by: Claude Sonnet 5 <noreply@anthropic.com>


## v2.4.1 (2026-07-01)

### 🐞 Bug Fixes

- **workflows**: Opt in to fork PR checkout, gate uv sync on scope check
  ([#155](https://github.com/after2400/liars-dice/pull/155),
  [`b5044e7`](https://github.com/after2400/liars-dice/commit/b5044e74da416fd1d82270f47ac1d4a1c808bfad))

## Summary
- `actions/checkout@v7` (landed in #137) added a default guard that refuses to check out fork PR code inside `pull_request_target` workflows unless `allow-unsafe-pr-checkout: true` is set — silently breaking `ruff`, `commitlint`, and `validate` for every fork-authored player PR (confirmed on #147, #150, #151).
- Sets `allow-unsafe-pr-checkout: true` on all 4 affected checkout steps, after individually auditing each job to confirm no token is exposed to the fork code it checks out.
- Reorders the `validate` and `register` jobs in `register-player.yml` so the players/-only scope check runs immediately after checkout, before `uv sync` — previously `uv sync` ran first, so a PR that also modified `pyproject.toml`/`uv.lock` would have that lockfile installed before either job's scope guard had a chance to reject it.

Full root-cause analysis, token-leakage audit, and the adjacent-risk trace are in #154.

Closes #154.

## Test plan
- [x] `just pytest-all` — 326 passed
- [x] `uv run ruff check .` — clean
- [x] YAML syntax validated (`yq eval '.'` on both files)
- [x] Bash syntax validated (`bash -n`) on all 4 extracted `run:` blocks
- [x] Functionally smoke-tested the scope-check script against real diffs for all 3 branches: no changes → skip, non-player files touched → skip, players/-only → proceed
- [ ] Confirm on a real fork PR after merge (existing open PRs #147/#150/#151 use `pull_request_target`, so they'll pick up this fix from `main` automatically on their next run — no need to touch those PRs directly)

Co-authored-by: Claude Sonnet 5 <noreply@anthropic.com>

### 🔁 Continuous Integration

- **workflows**: Fix auto-update skipping UNKNOWN-state player PRs
  ([#145](https://github.com/after2400/liars-dice/pull/145),
  [`4bce24f`](https://github.com/after2400/liars-dice/commit/4bce24f022763bd6132de6a0ae359145da81d208))

## Summary

- The auto-update workflow skipped PRs with `mergeStateStatus == UNKNOWN`, but GitHub computes merge state asynchronously — PRs are often `UNKNOWN` for several seconds after a push to main. This caused all 4 of DNiev's v2 migration PRs (#138, #139, #141, #142) to be skipped when #144 merged today.
- Fix: skip only `CLEAN` (already up-to-date) instead of requiring `BEHIND`. `UNKNOWN` and any other non-`CLEAN` status will now attempt `gh pr update-branch`, which handles both the up-to-date case (no-op) and the fork-restriction case (existing fallback comment) gracefully.
- Adds `workflow_dispatch` so the workflow can be triggered manually from the GitHub Actions UI without needing a push to main.

## Test plan

- [x] Merge this PR, then manually trigger the workflow from the Actions UI — confirm DNiev's 4 open PRs get updated
- [x] Verify the fork-restriction fallback comment still works for PRs from a fork's `main` branch (Columbo-style)


## v2.4.0 (2026-06-30)

### ✨ Features

- **game**: Split PlayerStatsPanel into focusable sub-panels with clipboard copy
  ([#144](https://github.com/after2400/liars-dice/pull/144),
  [`af3dadd`](https://github.com/after2400/liars-dice/commit/af3dadd03621ad17cf854ef828f3d878e31814af))

## Summary

- Split the monolithic `PlayerStatsPanel(Static)` into a container `Widget` holding two separately focusable children: `ThisWeekPanel` and `SimTotalPanel`
- Each child has `escape` (close) and `c` (copy to clipboard) keybindings
- `c` renders the panel as a structured plain-text Rich table — box-drawing characters preserved, zero ANSI codes — and pushes it to the clipboard via Textual's built-in `copy_to_clipboard()`
- `PlayerStatsPanel` buffers pre-mount `update_aggregate`/`update_step_data` calls and applies them in `on_mount()`, fixing a `MountError` when a player panel is drilled into after the simulation completes
- Fixed `StandingsWidget` cursor highlight: `bold reverse` now covers only the name/wins/win-pct columns; the bar chart column is unstyled so it stays visible on the selected row
- Updated `action_focus_panel` in `app.py` to cycle `ThisWeekPanel` and `SimTotalPanel` children rather than the outer container

Closes #143

## Test plan

- [ ] Run `just pytest-all` — 326 tests pass
- [ ] Start a sim, drill into a player, press `c` on each panel and verify clipboard content pastes with table structure intact
- [ ] Verify clicking each panel highlights only that panel (not both)
- [ ] Verify `escape` closes the drill-in from either child panel
- [ ] Drill into a player after the sim completes — no `MountError`
- [ ] Verify the selected row in the standings table shows the bar chart (not inverted/hidden)

### 🔁 Continuous Integration

- Upgrade actions to node24 runtimes ([#137](https://github.com/after2400/liars-dice/pull/137),
  [`ecc3e32`](https://github.com/after2400/liars-dice/commit/ecc3e32ede2729df193a44fe6e5c77f964a0e854))

Closes #136

Bumps `actions/checkout` v4→v7 and `astral-sh/setup-uv` v5→v8.2.0 across all 7 workflow files (16 references total). Both new versions target `node24`, eliminating the Node.js 20 deprecation warnings in CI.

Note: `astral-sh/setup-uv` does not publish floating major-version tags (no `v8` alias), so we pin to `v8.2.0` explicitly. `actions/checkout` does have a floating `v7` tag.

No breaking changes affect this repo — the only removed inputs (`server-url`, custom manifest format) are not used; all workflows only pass `python-version`.


## v2.3.0 (2026-06-30)

### ✨ Features

- **engine**: Use ctx.stats.ones_are_wild in Columbo
  ([#133](https://github.com/after2400/liars-dice/pull/133),
  [`e023de1`](https://github.com/after2400/liars-dice/commit/e023de1400c2a41dbe1d4ed01b324ef59ef55b38))

Replaces Columbo's `_wilds_active()` bet_history scan with a direct read of `ctx.stats.ones_are_wild` (added in #134), which the engine now maintains O(1) per turn.

cc @iappanaitis — no behavioural change.

Co-authored-by: Chuck Lunskis <cl@after2400.com>


## v2.2.0 (2026-06-30)

### ✨ Features

- **engine**: Add ones_are_wild to GameStats
  ([#134](https://github.com/after2400/liars-dice/pull/134),
  [`35802c7`](https://github.com/after2400/liars-dice/commit/35802c7fecbadfd004eca3fa1213921f46048b6b))

## Summary

- Adds `GameStats.ones_are_wild` — `True` unless the round-opening bid was on face 1
- Set in `update_bet` when `is_opening_bid=True`; reset to `True` in `reset_round`
- Removes the need for players to scan `bet_history` to determine wild mode each turn

## Why

8 players currently determine wild mode by filtering `ctx.bet_history` by game+round on every turn to find the opening bid face. `ones_are_wild` is computed once per bet by the engine and available as an O(1) read.

A follow-on player PR (#133) updates Columbo to use `ctx.stats.ones_are_wild`.

## Test plan

- [x] 5 new tests in `tests/test_stats.py`: default True, face-1 open → False, non-face-1 open → True, mid-round non-opening bid doesn't change it, `reset_round` restores True
- [x] `just pytest-all` — 314 passed


## v2.1.1 (2026-06-30)

### 🐞 Bug Fixes

- **scripts**: Sort tier standings by current-run results; pin relegated players to top
  ([#130](https://github.com/after2400/liars-dice/pull/130),
  [`8387989`](https://github.com/after2400/liars-dice/commit/8387989f778d6e20128750123bcd114b7edaac7a))

## Summary

- Per-tier standings (PRM, CH, L1) now rank players by their **this week's win%**, not QTD cumulative win%. Stewie's 18% QTD no longer overshadows Peter Beter winning this Monday 15.2%.
- Players relegated into a tier this week are **pinned to the top** of their new tier's table with `Relegated` in the Season W% column.
- `_update_readme` and `_write_summary` both thread `tier_results`/`n_games` through to `_standings_table` so the live README gets the same treatment.
- Two new tests: sort-by-run-results and relegated-player pinning.

Closes #129

## Test plan

- [x] `just pytest tests/test_run_season.py` — 19 tests pass
- [x] `just pytest-all` — 277 tests pass
- [x] Review `season_summary.md` to confirm Season W% reflects this run and relegated players appear at top of new tier

Co-authored-by: Claude Sonnet 4.6 <noreply@anthropic.com>


## v2.1.0 (2026-06-30)

### ✨ Features

- **engine**: Simulation replay — deterministic re-runs with diff reports
  ([#128](https://github.com/after2400/liars-dice/pull/128),
  [`f6fe703`](https://github.com/after2400/liars-dice/commit/f6fe70373ce23ca524982d8490f26d8e18f1f5ca))

## Summary

- Adds `ReplayDB` (SQLite) to record per-game seeds across all three simulation modes (`simulate-quarter`, `simulate-season`, `simulate-tournament`)
- `--save-replay` records seeds + leaderboard snapshot; `--replay <file>` replays them deterministically
- Diff reports compare original vs replay standings: season/quarter use tier win%, tournament uses pool win counts + tier assignments
- Fixes global `random` module non-determinism: `game_orchestrator` now seeds the global module from the same per-game seed, making players that call `random.random()` / `random.randint()` directly (e.g. Cleo, Rick, Nuke) fully reproducible on replay
- Regression test added for global-random player determinism
- TUI elapsed timer now stops when simulation completes, not when the user exits the TUI

## Test plan

- [x] `just pytest-all` — 307 tests pass
- [x] `just simulate-quarter --save-replay` then `just simulate-quarter
--replay sim-YYYY-QN.replay` — diff report shows all zeros
- [x] `just simulate-season <date> --save-replay` then replay — season diff shows real win% with zero deltas
- [x] `just simulate-tournament --save-replay` then replay — tournament diff shows pool wins + tier assignments with zero deltas
- [x] Confirm `sim-*-diff.md` is written for all three modes

---------

Co-authored-by: Claude Sonnet 4.6 <noreply@anthropic.com>


## v2.0.0 (2026-06-29)

### ✨ Features

- **engine**: V2.0.0 — SeriesResult API and Textual TUI
  ([#127](https://github.com/after2400/liars-dice/pull/127),
  [`055ae4b`](https://github.com/after2400/liars-dice/commit/055ae4b82263055a943ec26e6e65c814bbc9fcef))

## Summary

The squash merge title for #124 used `feat!(engine):` instead of `feat(engine)!:`. PSR requires `!` after the scope — with it before the scope, the breaking change wasn't detected and no release was generated.

This empty commit carries the correctly-formatted message + `BREAKING CHANGE:` footer so PSR produces v2.0.0 on merge.

## Test plan

- [x] `commitlint` passes locally
- [x] Merge → verify release workflow produces v2.0.0

---

---------

Co-authored-by: Claude Sonnet 4.6 <noreply@anthropic.com>


## v1.12.2 (2026-06-25)

### 🐞 Bug Fixes

- **engine**: Enter new players at lowest existing tier regardless of occupancy
  ([#117](https://github.com/after2400/liars-dice/pull/117),
  [`690edec`](https://github.com/after2400/liars-dice/commit/690edec04ae50c9306c3012de739724739efe57e))

Fixes #116

## Problem

`detect_entry_tier` found the lowest tier with *available capacity*, so in a 20-player league where `tier_capacities(21)` allocates an extra PRM slot, a brand-new player was placed directly in PRM. This is what happened to Meg Griffin — she registered at PRM, played one season (20/1000, 2%), and got relegated to CH before the bug was caught.

## Fix

Drop the occupancy check from the entry path. New players always enter at the lowest tier that **exists** (L1 for leagues of 9+ players; CH for very small leagues where L1 hasn't opened yet). A temporarily over-capacity tier is fine — the season run promotes/relegates to restore balance.

## Also in this PR

One-time leaderboard patch: Meg's entry reset to L1 with a clean `tier_stats: {}`, undoing the tainted PRM run.

## Tests updated

Three tests in `test_leaderboard.py` and two in `test_register_player.py` were encoding the old "find a tier with capacity" behaviour. All renamed and updated to assert the correct entry tier. Added a regression test for the exact 20-player scenario that triggered the bug.

---------

Co-authored-by: Claude Sonnet 4.6 <noreply@anthropic.com>


## v1.12.1 (2026-06-25)

### 🐞 Bug Fixes

- **engine**: Use display name in series results
  ([#115](https://github.com/after2400/liars-dice/pull/115),
  [`844b473`](https://github.com/after2400/liars-dice/commit/844b47312c61fee4ec48470d03b8b1fbdfddd004))

Fixes #114

`game/components/series.py` was keying win counts and log messages by `type(p).__name__` (Python class name) instead of `p.name` (the display name set by `apply_display_names` from the leaderboard). This meant the Series Results table showed e.g. `Meg` instead of `Meg Griffin`, inconsistent with the leaderboard and everything else.

**Changes:**
- `series.py`: replace `type(p).__name__` with `p.name` on lines 22, 42, 43
- `tests/test_main.py`: update `test_class_name_used_as_leaderboard_key` → `test_display_name_used_in_series_results`; set real `display_name` values in the fixture so `apply_display_names` produces the expected keys

Co-authored-by: Claude Sonnet 4.6 <noreply@anthropic.com>


## v1.12.0 (2026-06-25)

### ✨ Features

- **engine**: Add dice_counts to GameStats
  ([#111](https://github.com/after2400/liars-dice/pull/111),
  [`1cd1781`](https://github.com/after2400/liars-dice/commit/1cd178162e7a2457bd222cab15b1ca806be79949))

## Summary

- Adds `GameStats.start_game(player_names)` — called by the engine at the start of each game to initialize all players to 5 dice
- Adds `GameStats.dice_counts` property — returns `dict[str, int]` copy of current per-player die counts
- Updates `update_outcome` to sync counts from round-start hand sizes and decrement the loser
- Calls `start_game` in `game_orchestrator` after the player shuffle, so counts are valid from turn 1

Closes #110

## Test plan

- [x] `just pytest tests/test_stats.py` — 7 new tests covering init, `start_game`, loser decrement, shrinking hands across rounds, between-game reset, and copy safety
- [x] `just pytest-all` — 218/218

---------

Co-authored-by: Claude Sonnet 4.6 <noreply@anthropic.com>


## v1.11.0 (2026-06-20)

### ✨ Features

- **scripts**: Scan v1 players in weekly season summary
  ([#107](https://github.com/after2400/liars-dice/pull/107),
  [`d252f5f`](https://github.com/after2400/liars-dice/commit/d252f5fb1a5a7bafe53532278bc2a2631f4520f0))

## Summary

- Adds `_scan_v1_players()` to `run_season.py` — inspects each registered player's `algo()` signature using `inspect.signature` (same logic as the engine dispatch)
- Prints `[warn] v1 algo() players (N): ...` to stdout on every Monday CI run
- Appends a **Migrate to v2 before 2026-10-05** section to the season summary comment posted to the tracking issue, listing v1 players by display name
- Section is omitted automatically once all players migrate

Currently 11 registered players are on v1: Alice, Bruno, Cal Culatid, Cleo, Deep Thought, Diego, Honest Abe, Peter Beter, Peter Griffin, Rick Sanchez, Stewie.

Relates to #106.

## Test plan

- [x] `just pytest-all` — 211 passed
- [x] Smoke-tested `_scan_v1_players` logic directly against current `leaderboard.yaml` — returns correct 11 players

Co-authored-by: Claude Sonnet 4.6 <noreply@anthropic.com>


## v1.10.0 (2026-06-20)

### ✨ Features

- **game**: GameContext v2 — immutable context object for algo() (#82)
  ([#83](https://github.com/after2400/liars-dice/pull/83),
  [`9169321`](https://github.com/after2400/liars-dice/commit/916932111231943da8ecb9e1f41c98018ede0c36))

Closes #82

## Summary

- Introduces `GameContext` — a single immutable object replacing the growing list of opt-in kwargs on `algo()`
- `bet_history` and `outcomes` exposed as `_ReadOnlySequence` — a live O(1) proxy over the shared accumulator list (no copying). Dict entries returned as `MappingProxyType` on access; container has no `append`/`pop`/`clear`
- Adds v1/v2 dispatch in the engine: `def algo(self, ctx)` → v2 path; positional args → v1 path unchanged
- Adds deprecation warning in `validate.py` for v1 players; hard cutover 2026-10-05
- Updates Player Guide wiki and CONTRIBUTING.md with v2 API reference and migration guide

## What changed

| File | Change | |---|---| | `game/components/context.py` | New — `_ReadOnlySequence` + `GameContext` with `__slots__` and `__setattr__` guard | | `game/components/script.py` | `_ReadOnlySequence` wrappers created once per game; `_is_v2` detection + dual dispatch | | `game/validate.py` | v2 signature accepted; v1 emits deprecation warning to stdout (exit 0); `round_players` added to allowed opts | | `tests/test_context.py` | Full coverage of `_ReadOnlySequence` and `GameContext` immutability | | `tests/test_main.py` | v1/v2 coexistence and field population tests | | `tests/test_validate_player.py` | Deprecation warning tests | | `docs/wiki/Player-Guide.md` | v2 API table, deprecation banner, migration guide | | `CONTRIBUTING.md` | Deprecation note with cutover date and wiki link |

## Performance

Before: `list(bet_history)` + `list(outcomes)` copied on every player turn — O(n), growing to ~30k entries by game 1000. After (v2 players): `_ReadOnlySequence` wrapper created once per game (O(1)), shared across all turns.

## Breaking change (v1 players)

`outcome["hands"]["PlayerName"]` is now a `tuple` instead of a `list`. Indexing and iteration unchanged; `.sort()` / `.append()` require `sorted()`. Documented in the migration guide.

## Test plan

- [x] `just pytest-all` — 213 passed, 0 failures
- [x] Rebased onto current main

---

---------

Co-authored-by: Claude Sonnet 4.6 <noreply@anthropic.com>


## v1.9.0 (2026-06-19)

### ✨ Features

- **game**: Add step counter, elapsed time, and generated-at timestamp to quarter sim
  ([#94](https://github.com/after2400/liars-dice/pull/94),
  [`46c24c7`](https://github.com/after2400/liars-dice/commit/46c24c7ded452206ccef16d478c71b4e60f86220))

## Summary

- Step separator now shows `(week N/total)` so you know where you are in a long run
- Each step prints `[simulate] done in X.Xs` after its subprocess completes
- Final line prints `[simulate] total elapsed: X.Xs` after the report is written
- Report header gains a `**Generated:** YYYY-MM-DD HH:MM:SS` field

Single file changed: `game/simulation/quarter.py`

Closes #89

---------

Co-authored-by: Claude Sonnet 4.6 <noreply@anthropic.com>

### 🔁 Continuous Integration

- **workflows**: Add workflow_dispatch to sync-wiki for manual triggers
  ([#91](https://github.com/after2400/liars-dice/pull/91),
  [`c36c450`](https://github.com/after2400/liars-dice/commit/c36c450c500a615ca4926c32b5632ef0bcfd8447))

## Summary

Adds `workflow_dispatch` to the Sync Wiki workflow so it can be triggered manually from the Actions UI — useful when wiki content is already on main but the sync needs to be re-run (e.g. after a permissions fix like #90).

---

- **workflows**: Auto-update player PR branches when main advances
  ([#93](https://github.com/after2400/liars-dice/pull/93),
  [`cd43d3c`](https://github.com/after2400/liars-dice/commit/cd43d3cda48b9f2fc8aefab5c74f467f9b53d852))

## Summary

- Adds `.github/workflows/auto-update-player-prs.yml` — triggers on every push to `main`
- Finds all open PRs that touch only `players/*.py`
- Calls `gh pr update-branch` on any that are `BEHIND`, so auto-merge can proceed without contributor intervention
- Skips PRs touching non-player files and PRs with conflicts (`DIRTY`) — those still need human attention
- Uses `LEADERBOARD_PAT` (same token as the register step) for fork branch update permission

Closes #92

Co-authored-by: Claude Sonnet 4.6 <noreply@anthropic.com>

- **workflows**: Grant contents: write so GITHUB_TOKEN can push to wiki
  ([#90](https://github.com/after2400/liars-dice/pull/90),
  [`b52bd81`](https://github.com/after2400/liars-dice/commit/b52bd81a4ea36ccf9004e4391bfbc268ddea8081))

## Summary

The sync-wiki workflow was failing with:

``` remote: Permission to after2400/liars-dice.wiki.git denied to github-actions[bot].

fatal: unable to access '...': The requested URL returned error: 403 ```

The workflow had `permissions: contents: read`, which blocked the push to the wiki repo. `GITHUB_TOKEN` needs `contents: write` to push to `<repo>.wiki.git`.

Fixes the failure from https://github.com/after2400/liars-dice/actions/runs/27826320371/job/82351569505

---

### 📖 Documentation

- Add local simulation workflow to Player Guide wiki
  ([#88](https://github.com/after2400/liars-dice/pull/88),
  [`5e758f1`](https://github.com/after2400/liars-dice/commit/5e758f1796c5464dc04da04f7ce44aa8e187c15c))

## Summary

Adds a "Simulating a season" subsection to **Testing Locally** in `docs/wiki/Player-Guide.md`, covering the three-step workflow now that `just register-player` (#84) and `just simulate-quarter` (#87) both exist:

1. `just register-player` — register the bot locally 2. `just simulate-tournament` / `just simulate-season` / `just simulate-quarter` — pick a scope 3. `just clean` — restore leaderboard afterward

Closes #85

---


## v1.8.0 (2026-06-19)

### ✨ Features

- **scripts**: Add just simulate-quarter recipe and optional path to just clean
  ([#87](https://github.com/after2400/liars-dice/pull/87),
  [`743c689`](https://github.com/after2400/liars-dice/commit/743c6895689f5d1f7e1dfb0f81263ae4bc175340))

## Summary

- Adds `just simulate-quarter [start] [n-games]` recipe — wraps `uv run python -m game.simulation.quarter` with optional `--start` and `--n-games` args
- Extends `just clean` with an optional `path` arg (defaults to `.`) so worktree simulations can be cleaned without a manual `git -C <path> checkout`
- Updates CLAUDE.md to reflect both recipes and replaces the raw `uv run python` register incantation with `just register-player`

Closes #81

---

### 📖 Documentation

- Add just register-player recipe and document local registration
  ([#84](https://github.com/after2400/liars-dice/pull/84),
  [`cbdb237`](https://github.com/after2400/liars-dice/commit/cbdb237ad6c41d037453652c441dd3e628ec58c7))

## Summary

- Adds `just register-player <file> <username>` recipe to `.Justfile` (hardcoded `DRY_RUN=1`)
- Documents local player registration in `CONTRIBUTING.md`, including the class-name-must-match-filename rule

Closes #74

---


## v1.7.0 (2026-06-19)

### ✨ Features

- **game**: Add round_players opt-in kwarg to algo() (#75)
  ([#78](https://github.com/after2400/liars-dice/pull/78),
  [`6bb7d1d`](https://github.com/after2400/liars-dice/commit/6bb7d1de71b2638009ea9642c9fc7ee49bdd66be))

## Summary

- Adds `round_players: list[str] | None` as an opt-in kwarg to `algo()`, detected via `inspect.signature` (same pattern as `stats` and `tier`)
- `round_players[0]` is always the opening bidder; the list reflects only active players for the current round and shrinks as players are eliminated
- Also restructures `just pytest` recipes: new `just pytest *args` for targeted runs, `just pytest-players` replaces the old `just pytest` sandbox recipe

## Changes

- `game/components/script.py` — compute `round_players_order` once per round; inject via kwargs for players that declare it
- `tests/test_main.py` — two new tests: kwarg is passed as a list, and `round_players[0]` is the opener
- `.Justfile` — three recipes: `just pytest *args`, `just pytest-players`, `just pytest-all`
- `CLAUDE.md` / `CONTRIBUTING.md` — docs updated for new recipe names
- Wiki `Player-Guide.md` — `round_players` added to signature stub and API table (pushed directly)

Closes #75

## Test plan

- [ ] `just pytest-all` — 172 tests pass
- [ ] `just pytest tests/test_main.py::test_round_players_passed_when_declared` — passes
- [ ] `just pytest tests/test_main.py::test_round_players_first_element_is_opener` — passes

### 🔁 Continuous Integration

- Sync docs/wiki/ to GitHub wiki on merge (#79)
  ([#80](https://github.com/after2400/liars-dice/pull/80),
  [`1f07f57`](https://github.com/after2400/liars-dice/commit/1f07f57bc1695e619ab6fcbdd2316fb1c66298ae))

## Summary

- Moves wiki source files into `docs/wiki/` (Home, Rules, Player-Guide) — the main repo is now the single source of truth
- Adds `.github/workflows/sync-wiki.yml` — triggers on push to `main` when `docs/wiki/**` changes, clones the wiki repo, copies files, commits and pushes
- Each wiki page gets a `<!-- source: docs/wiki/FileName.md -->` header so direct editors know where changes belong
- Uses `GITHUB_TOKEN` — no extra secrets needed

## Effect

All wiki changes now go through normal PRs with diff review and commit history. The wiki URL is unchanged for players. Direct edits to the wiki will be silently overwritten on the next `docs/wiki/` merge to main.

`docs/wiki/Player-Guide.md` already includes the `round_players` update from #75/#78.

Closes #79

## Test plan

- [ ] Merge this PR and confirm the sync-wiki workflow runs and pushes to the wiki
- [ ] Make a small edit to `docs/wiki/Home.md` in a follow-up PR and confirm the wiki updates on merge


## v1.6.2 (2026-06-18)

### 🐞 Bug Fixes

- **game**: Grow PRM/CH to 8 before L1 resumes growth
  ([#76](https://github.com/after2400/liars-dice/pull/76),
  [`34f1122`](https://github.com/after2400/liars-dice/commit/34f112247686ae5c220d780bfaddaabf8f16a42e))

## Summary

Changes the tier capacity growth path so L1 freezes at 8 while PRM and CH catch up, rather than L1 absorbing all new players until capped.

- `tier_capacities`: new phase splits the old `≤24` branch — L1 holds at 8 for n=17–24 while PRM/CH alternate up one seat each
- `detect_entry_tier`: uses L1's true growth trajectory (`n-8` capped at 16) so new players always enter L1, not PRM/CH
- `settle_relegations`: same fix — L1's true capacity used to prevent spurious relegation during the freeze phase

## Growth path

| n | PRM | CH | L1 | |---|-----|----|----| | 16 | 4 | 4 | 8 | ← now (unchanged) | | 18 | 5 | 5 | 8 | | 20 | 6 | 6 | 8 | | 24 | 8 | 8 | 8 | | 28 | 8 | 8 | 12 | | 32 | 8 | 8 | 16 |

## Test plan

- [x] Engine tests: `just pytest-all` — 169 passed
- [x] Locally registered players 17–25 one at a time, ran a season after each — every player entered L1, PRM/CH grew correctly, season ran clean at every step
- [x] Player 25 entered L1 with PRM=8/CH=8 locked ✓

Closes #73


## v1.6.1 (2026-06-18)

### 🐞 Bug Fixes

- **config**: Update simulate-tournament to use game.season.utils
  ([#72](https://github.com/after2400/liars-dice/pull/72),
  [`d218a84`](https://github.com/after2400/liars-dice/commit/d218a8498294f7748dc3bdd9d35ac40b19a96d3a))

## Summary

- Fixes broken `just simulate-tournament` recipe — `season_utils` moved from `.github/scripts/` to `game/season/utils.py` when the engine was restructured, but the Justfile was never updated
- Replaces the old `sys.path.insert` hack with a clean two-step: get the next tournament Monday from `game.season.utils`, then invoke `reset_season.py` with `TODAY=` set

## Test plan

- [x] `just simulate-tournament` runs to completion (verified locally)
- [x] `just simulate-season` unaffected
- [x] `just clean` restores `leaderboard.yaml` after

---

Co-authored-by: Claude Sonnet 4.6 <noreply@anthropic.com>


## v1.6.0 (2026-06-18)

### ✨ Features

- **game**: Split L1 into pools when >8 players for season runs
  ([#70](https://github.com/after2400/liars-dice/pull/70),
  [`9e3e982`](https://github.com/after2400/liars-dice/commit/9e3e982153f58831f3ee19c5481ce3067c71969b))

## Summary

- When L1 has more than 9 players, splits into S-curve seeded pools of ≤9 before running games
- Combined win counts rank all L1 players globally for promotion/relegation — same approach as the quarterly tournament
- Single-pool path (≤9 players) is unchanged — 8 existing + 1 new player runs as a single pool of 9 as designed
- Moves `form_pools()` from `reset_season.py` → `game/season/utils.py` so both scripts share the same implementation

## Why

The \"8 + newbie = 9\" single-pool scenario is fair. Pool splitting becomes necessary when L1 grows beyond 9 (10+ players), which happens around the 18th registered player depending on tier dynamics. At that point, splitting into pools of ≤9 gives each player a tighter, fairer game while still producing a global L1 ranking.

## Pool size table

| L1 players | Pools | Pool sizes | |---|---|---| | ≤9 | 1 | single pool | | 10 | 2 | [5, 5] | | 16 | 2 | [8, 8] | | 17 | 2 | [9, 8] | | 18 | 2 | [9, 9] | | 19 | 3 | [7, 6, 6] |

## How it works

``` L1: 10 players → 2 pools of ≤9, 1000 games each …

[pool 1/2]: [Alice, Cleo, Finn, Remy, Topper]
  [pool 2/2]: [Bruno, Pyro, Rick, NewPlayer1, NewPlayer2] ```

Win counts from both pools combined → ranked globally → top promotes to CH, bottom relegated to DED.

## Test plan

- [ ] 168 tests passing ✅
- [ ] Merge and watch next season run — L1 has 8 players so single-pool path runs; verify no regression
- [ ] Pool splitting fires when L1 reaches 10+ players (~18th registered player)

---------

Co-authored-by: Claude Sonnet 4.6 <noreply@anthropic.com>


## v1.5.1 (2026-06-18)

### 🐞 Bug Fixes

- **game**: Scale tier capacity with player count in settle_relegations
  ([#71](https://github.com/after2400/liars-dice/pull/71),
  [`05af5e6`](https://github.com/after2400/liars-dice/commit/05af5e6d4b3c670722e9439d6419e4fe2f9c58aa))

## Summary

- `settle_relegations` now uses `max(tier_capacities(n_players), _TIER_CAPACITY(tier, top_n))` for capacity
- PRM and CH grow from 4→8 players as the league scales from 24→32 registered players, instead of staying locked at 4
- `_TIER_CAPACITY` floor preserved so small test fixtures continue to work

## Why

`_TIER_CAPACITY(tier, top_n)` returns `top_n` (4) for PRM and CH regardless of league size. `tier_capacities(n_players)` correctly scales them from 4→8 as total players grow 24→32. Without this fix, at 26 registered players the season runner would see PRM/CH as over capacity by 1 and relegate a player from each every single run — permanently draining the top tiers.

## Merge order

Merge before or alongside PR #70 (L1 pool splitting) — both are safe independently but this fix is needed before the league reaches 25 registered players.

Co-authored-by: Claude Sonnet 4.6 <noreply@anthropic.com>


## v1.5.0 (2026-06-18)

### ✨ Features

- **workflows**: Trigger season run automatically after new player registers
  ([#69](https://github.com/after2400/liars-dice/pull/69),
  [`d3bfbce`](https://github.com/after2400/liars-dice/commit/d3bfbce0b7609cb0ee58d03214ca95ad477fdc61))

## Summary

- After a new player PR merges and `update-leaderboard.yml` registers them, it now automatically dispatches `run-season.yml`
- Only fires for new player additions (not modifications or deletions)
- Combines with the `season-run` concurrency group (PR #67) — back-to-back player merges queue their season runs rather than race

## Why

Previously new players waited until the next scheduled daily run (up to 24h) to compete. With multiple players merging the same day, only 1 could promote per run regardless of merit. Each player now gets an immediate individual shot at promotion based on the roster at the time they join.

## How it works

1. Player PR merges → `update-leaderboard.yml` fires 2. Player registered into `leaderboard.yaml`, committed, pushed 3. `player_added` output set → dispatches `run-season.yml` 4. Season run queues behind any in-progress run (concurrency group) 5. Season runs, new player competes, settles into earned tier

Co-authored-by: Claude Sonnet 4.6 <noreply@anthropic.com>


## v1.4.8 (2026-06-18)

### 🐞 Bug Fixes

- **workflows**: Serialize concurrent workflow runs
  ([#67](https://github.com/after2400/liars-dice/pull/67),
  [`a25962c`](https://github.com/after2400/liars-dice/commit/a25962ce8f5b1cd5c62282ba50b0080d4984a58f))

## Summary

- Adds `concurrency` group to `update-leaderboard.yml` so back-to-back player PR merges queue rather than race each other mutating `leaderboard.yaml`
- Adds `concurrency` group to `run-season.yml` so two season runs triggered in quick succession queue rather than conflict
- `cancel-in-progress: false` on both — second run waits for first to finish, not cancelled

## Why

When multiple player PRs merge within seconds of each other, both workflows fire concurrently against the same `leaderboard.yaml`. Without serialization, the later run can read stale state, overwrite the first run's registration, or produce a corrupted leaderboard commit. This is groundwork for the per-merge season run design.

## Test plan

- [ ] Verify lint passes
- [ ] Merge two player PRs in quick succession and confirm second workflow run shows as "queued" not running in parallel

Co-authored-by: Claude Sonnet 4.6 <noreply@anthropic.com>


## v1.4.7 (2026-06-18)

### 🐞 Bug Fixes

- **scripts**: Add time to season summary heading
  ([#68](https://github.com/after2400/liars-dice/pull/68),
  [`8016cce`](https://github.com/after2400/liars-dice/commit/8016ccede7f1971abc494ec56d69f4695943cedc))

## Summary

- Season summary issue comments now include time: `# Season Summary — 2026-06-17 14:32 UTC`
- Previously all runs on the same day produced identically-titled comments

## Why

With per-player-merge season runs coming, multiple runs on a single day will be the norm. The timestamp makes each comment distinguishable in the tracking issue without requiring any state tracking.

Co-authored-by: Claude Sonnet 4.6 <noreply@anthropic.com>

### 🏗 Chores

- **leaderboard**: Attribute Alice, Bruno, Cleo, Diego to zachaustin01
  ([#65](https://github.com/after2400/liars-dice/pull/65),
  [`0eff6bf`](https://github.com/after2400/liars-dice/commit/0eff6bfed30c862ade5359f65c8630bb89629822))

## Summary

- Sets `github_username: zachaustin01` on Alice, Bruno, Cleo, and Diego — the four original placeholder bots zachaustin01 initially created
- These were left with an empty username when the project was first set up; now that zachaustin01 is a collaborator with proper docs attribution, this catches the leaderboard up

## Test plan

- [x] No logic changes — single-field data update, verified diff is exactly 4 lines


## v1.4.6 (2026-06-18)

### 🐞 Bug Fixes

- **game**: Phase 3 operational hardening ([#64](https://github.com/after2400/liars-dice/pull/64),
  [`1297d9c`](https://github.com/after2400/liars-dice/commit/1297d9c9c8d9a52d899816da99cb435cf2f48b87))

## Summary

Three operational hardening items closing out the 2026-06-17 security audit.

**Leaderboard write isolation** (`run_season.py`, `reset_season.py`)
- `chmod 444` the leaderboard before spawning each game engine subprocess; `chmod 644` restored in a `finally` block so permissions are always cleaned up even on failure
- Without this, a bot running inside `python -m game` could open and overwrite `leaderboard.yaml` mid-run — and because `apply_season_results()` re-reads from disk, the tampered state would be picked up before standings are written back

**Instantiation timeout** (`game/validate.py`)
- 10-second `SIGALRM` deadline wraps `player_class()` in the runtime validation phase
- A bot with an infinite loop or blocking call in `__init__` no longer ties up the Actions runner indefinitely; exits 1 with a clear "timed out during instantiation" message

**Full crash traceback logging** (`game/components/script.py`)
- The exception handler on `algo()` now logs `traceback.format_exc()` rather than just the exception message
- Makes intentional strategic crashes (raise on a good turn) distinguishable from bugs when reviewing `gamelog.log`

Closes #61

## Test plan

- [x] `just pytest-all` — 168/168 passing (including new `test_init_timeout` which verifies the SIGALRM fires and exits within the deadline)
- [x] All pre-commit hooks pass


## v1.4.5 (2026-06-18)

### 🐞 Bug Fixes

- **game**: Replace exec_module() with AST-based player validator
  ([#63](https://github.com/after2400/liars-dice/pull/63),
  [`062ee54`](https://github.com/after2400/liars-dice/commit/062ee54a4a346219965015311328d43719a9591c))

## Summary

Replaces the current `exec_module()` import-and-inspect pattern in `game/validate.py` with a two-phase approach that eliminates the CI token exfiltration surface and in-game call-stack inspection attacks identified in the 2026-06-17 security audit.

**Phase 1 — AST analysis (no code execution):**
- **Import whitelist** enforced everywhere in the file (not just at module level): only `game.components.bets`, `game.components.stats`, and a curated set of safe stdlib packages (`math`, `random`, `logging`, `typing`, `collections`, `itertools`, `copy`, `dataclasses`, `enum`, `functools`, `operator`, `abc`, `types`). Blocks `os`, `sys`, `inspect`, `gc`, `socket`, `subprocess`, `requests`, `urllib`, `ctypes`, etc.
- **Blocked builtins** everywhere in the file: `exec`, `eval`, `__import__`, `compile`, `open` — closes the no-import bypass via `exec('import os; ...')`.
- **Module-level executable statements** (bare calls, `raise`, loops, `try`/`with` blocks) are rejected. Assignments are allowed so `logger = logging.getLogger(__name__)` works.
- Class name / `algo` signature / display name validated structurally.

**Phase 2 — runtime (only if Phase 1 passes):**
- `exec_module()` — now safe because all imports are whitelisted
- Instantiation — catches crashing `__init__`
- `tier=None` probe — catches players that crash on `None`

**Vectors closed:**
- Module-level code exfiltrating `GITHUB_TOKEN` during CI validation (#60)
- `import inspect; inspect.stack()` reading current-round hidden dice (#60 / audit item 3)
- Any `import os`, `import gc`, `import subprocess`, `import socket`, etc.
- `exec()`/`eval()` builtins as no-import bypass

**Unchanged behaviour for legitimate players:** all existing `players/*.py` files pass. The `test_all_real_players` test enforces this going forward.

Closes #60

## Test plan

- [x] `just pytest-all` — 167/167 passing
- [x] New: `test_module_level_exec` — bare `raise` at module level rejected
- [x] New: `test_blocked_import` — `import os` rejected with "not allowed"
- [x] New: `test_blocked_import_inside_method` — `import inspect` inside `algo()` rejected
- [x] New: `test_all_real_players` — every player in `players/` passes (regression guard)
- [x] New: `test_valid_player_with_allowed_imports` — `math`, `random`, `logging`, `game.components.bets` all accepted


## v1.4.4 (2026-06-18)

### ⚡️ Performance Improvements

- **game**: Isolate algo() inputs from shared game state
  ([#62](https://github.com/after2400/liars-dice/pull/62),
  [`56d0850`](https://github.com/after2400/liars-dice/commit/56d085055c53171566f1da974f02f0c3efe094a8))

## Summary

- Passes a fresh `Bet` copy, `list(bet_history)`, `list(completed_outcomes)`, and `list(hand)` to every `algo()` call so a malicious bot cannot mutate shared round state and affect subsequent players in the same round
- Seeds each game's RNG with `secrets.randbits(64)` rather than the unseed global `random` state, closing seed-inference attacks

Part of the security hardening audit (2026-06-17):
- Phase 1 (this PR): mutable refs + RNG seed
- Phase 2 (#60): AST-based validator — closes CI exfiltration surface
- Phase 3 (#61): Operational hardening

Closes #59

## Test plan

- [x] `just pytest-all` — 163/163 passing
- [x] All pre-commit hooks pass (ruff, commitlint)

### 📖 Documentation

- Migrate player docs to wiki, trim CONTRIBUTING.md
  ([#57](https://github.com/after2400/liars-dice/pull/57),
  [`c25d4b0`](https://github.com/after2400/liars-dice/commit/c25d4b00a313e3b96f9c396a1cba5f1da7123340))

Closes #53

## Summary

- **README**: replaces the `CONTRIBUTING.md` · `RULES.md` link pair with a single prominent **[Visit the Wiki](https://github.com/after2400/liars-dice/wiki)** link. Dev setup pointer to `CONTRIBUTING.md` is retained.
- **CONTRIBUTING.md**: stripped down to local dev setup only (tests, simulation, running games). The player-facing sections (Adding a Player, Player API) are now on the wiki and linked from the top of the file.
- **RULES.md**: deleted — content fully migrated to [wiki/Rules](https://github.com/after2400/liars-dice/wiki/Rules).

## Wiki pages created

- [Home](https://github.com/after2400/liars-dice/wiki) — overview + navigation
- [Rules](https://github.com/after2400/liars-dice/wiki/Rules) — game rules
- [Player Guide](https://github.com/after2400/liars-dice/wiki/Player-Guide) — full authoring guide + API reference

## Test plan

- [x] README wiki link renders and lands on the correct wiki home page
- [x] CONTRIBUTING.md wiki link at the top is visible and correct
- [x] All three wiki pages render cleanly on GitHub

Co-authored-by: Claude Sonnet 4.6 <noreply@anthropic.com>


## v1.4.3 (2026-06-17)

### 🐞 Bug Fixes

- **ci**: Support fork PRs — switch register-player to pull_request_target
  ([#55](https://github.com/after2400/liars-dice/pull/55),
  [`00612b0`](https://github.com/after2400/liars-dice/commit/00612b0530f985432ac43d638adee363c333282c))

Closes #52

## Problem

External contributors who fork the repo and open a player PR hit two failures with the `pull_request` trigger:

1. **`LEADERBOARD_PAT` is inaccessible** — GitHub blocks all repository secrets for fork PRs. The `register` job's `gh pr merge` call silently fails with no token. 2. **Checkout ref doesn't resolve** — `github.head_ref` is the fork's branch name (e.g. `add-my-player`), which doesn't exist in the base repo. The checkout step errors before validation runs.

## Fix

**Switch to `pull_request_target`** — runs in the base repo's context for all PRs (including forks), so secrets are available.

**Update checkout ref** — both jobs now use `github.event.pull_request.head.sha` instead of `github.head_ref`, which correctly fetches the fork's code.

**Split the validate step** — with `pull_request_target` the GITHUB_TOKEN has write access, so it's important that it not be in the environment when fork code runs. The validate step now has zero tokens exposed; a separate comment step (runs only on failure) holds `GH_TOKEN`.

**`persist-credentials: false` on the validate checkout** — `actions/checkout` stores the auth token in git's credential helper by default. A malicious player file could extract it via `git credential fill`. Clearing credentials after checkout closes this vector. (The `register` job retains credentials since it runs no fork code.)

**Document the fork path** — added a note to CONTRIBUTING.md for contributors without write access.

## Security notes

- The `validate` job runs player code but holds no secrets — same as before, now made explicit by the step split and credential clearing.
- The `register` job has `LEADERBOARD_PAT` but runs no fork code — same as before.
- `pull_request_target` is safe here specifically because this privilege separation was already in place.
- Dependencies (`pyproject.toml`, `uv.lock`) always come from the base repo's admin-controlled branch, not the fork.

## Test plan

- [ ] Fork the repo, add a valid player file, open a PR — workflow should validate and auto-merge
- [ ] Fork the repo, add an invalid player file — should get a PR comment with the validation error
- [ ] Same-repo player PRs (admin) still work as before

---------

Co-authored-by: Claude Sonnet 4.6 <noreply@anthropic.com>

### 📖 Documentation

- Rename Run Monday → Run Season, add attribution, fix pytest docs
  ([#54](https://github.com/after2400/liars-dice/pull/54),
  [`181f518`](https://github.com/after2400/liars-dice/commit/181f5187c2b9209b2d6da3f4e721aa418121435d))

## Summary

- **Rename `run-monday.yml` → `run-season.yml`** — the workflow name and internal `--workflow=` reference. The filename was renamed when we scoped it to Mondays, but now that it fires on any day a new player joins, "Run Season" is the accurate name again. The README already referenced `run-season.yml` (never updated during the rename), so no README change needed there.
- **Add attribution** — Zach Austin ([@zachaustin01](https://github.com/zachaustin01)) credited in README for foundational work and initial implementation.
- **Clarify `just pytest` vs `just pytest-all`** in CONTRIBUTING.md — the previous description said "full test suite" which was misleading; `just pytest` only covers `player_tests/`, while `just pytest-all` runs the engine suite too.

## Test plan

- [x] Verify `run-season.yml` appears in Actions tab after merge
- [x] Confirm `Run Season` is the workflow display name in GitHub Actions
- [x] Check README renders attribution correctly on the repo landing page

---------

Co-authored-by: Claude Sonnet 4.6 <noreply@anthropic.com>


## v1.4.2 (2026-06-16)

### 🐞 Bug Fixes

- **workflows**: Run daily and pick up new players since last run
  ([#49](https://github.com/after2400/liars-dice/pull/49),
  [`229d856`](https://github.com/after2400/liars-dice/commit/229d856518234895f8a97546acf2532af0594a8b))

## Summary

Replaces the immediate `workflow_dispatch` approach from #47 with a daily cron that checks for new players before firing.

- **`run-monday.yml`**: cron changed from `0 9 * * 1` (Monday-only) to `0 9 * * *` (daily). Non-Monday guard now queries the last successful run timestamp via `gh run list` and checks `git log --since=<that timestamp>` for new player files. Falls back to a 48h window if no prior run exists. Adds `actions: read` permission for the API call.
- **`update-leaderboard.yml`**: reverts the #47 dispatch additions (`actions: write` permission, `LEADERBOARD_PAT` env var, `gh workflow run` call).

**Behavior:**
- Player merges Monday → registered, picked up by the 9am UTC cron as before
- Player merges any other day → registered, next-day 9am UTC run detects them and fires a season run
- 3 players merge on the same day → all registered, single run the following morning
- No player additions → daily cron checks and skips (no games, no issue comment)

Closes #48

## Test plan

- [ ] Player merges on a non-Monday — confirm next-day 9am UTC run fires with `mode=season`
- [ ] No new players — confirm daily cron outputs "No new players since last run — skipping" and the `run` job is skipped
- [ ] Monday run still works normally

Co-authored-by: Claude Sonnet 4.6 <noreply@anthropic.com>


## v1.4.1 (2026-06-16)

### 🐞 Bug Fixes

- **workflows**: Dispatch season run when new player added on non-Monday
  ([#47](https://github.com/after2400/liars-dice/pull/47),
  [`6379e22`](https://github.com/after2400/liars-dice/commit/6379e228ddcda030e90a43ffebc4619b5fb85381))

## Summary

- `update-leaderboard.yml` now dispatches `run-monday.yml` via `LEADERBOARD_PAT` when a player file is added on a non-Monday day
- Suppressed on Mondays — the scheduled cron already covers same-day player additions
- Uses `LEADERBOARD_PAT` (not `GITHUB_TOKEN`) because GitHub blocks workflow-triggered workflows to prevent loops
- Removes the dead `New player file(s)` branch in `run-monday.yml` that logged a distinct message but wrote the same `mode=season` output as the regular Monday branch

**Note:** `LEADERBOARD_PAT` must have the `workflow` scope for the dispatch to succeed.

Closes #46

## Test plan

- [ ] Merge a player PR on a non-Monday and confirm `update-leaderboard.yml` dispatches `run-monday.yml`
- [ ] Confirm the dispatched run plays games and posts a summary to the tracking issue
- [ ] Merge a player PR on a Monday and confirm no extra dispatch (cron handles it)

Co-authored-by: Claude Sonnet 4.6 <noreply@anthropic.com>


## v1.4.0 (2026-06-16)

### ✨ Features

- Deduplicate player display names in-game when they collide
  ([#45](https://github.com/after2400/liars-dice/pull/45),
  [`0cd15e2`](https://github.com/after2400/liars-dice/commit/0cd15e25dba43c44fabb2a31733c2aaf1a344576))

## Summary

- Adds `apply_display_names(players, lb_players)` to `game/components/utils.py` — wraps `build_display_names` and writes the deduplicated name back to each player object
- Calls it in `game/__main__.py` immediately after loading players from disk, before any games run
- When two players share a `name` attribute, each gets a `(github_username)` suffix so `prior_bet.player` is always unique — both for opponent-modelling bots and `GameStats` keys

Previously `build_display_names` deduplication only applied to the leaderboard/README reporting layer. In-game, `prior_bet.player` carried the raw class `name` attribute, making collision detection by bots impossible.

Closes #36

## Test plan

- [ ] `TestApplyDisplayNames` (4 tests): unit-tests the new function — deduplication, unique names unchanged, unregistered players skipped, deduplicated name in `bet_history`
- [ ] `just pytest-all` — all 163 tests pass

---

Co-authored-by: Claude Sonnet 4.6 <noreply@anthropic.com>

### 🔁 Continuous Integration

- Skip auto-merge for admin player PRs ([#40](https://github.com/after2400/liars-dice/pull/40),
  [`c4fda4d`](https://github.com/after2400/liars-dice/commit/c4fda4de6ca9abf3e90b5fb8ec9fc355c5841f60))

Admin-submitted `players/` PRs now post a ✅ comment and require a manual merge click. Community contributor PRs continue to auto-merge as before.

## Why Admin player PRs represent in-house bots that need explicit sign-off before entering the league — we don't want a CI push to automatically debut a player that isn't ready. This came up when Nuke LaLoosh was accidentally auto-merged before simulation was complete (#39).

## What changed
- `register-player.yml`: hoisted `is_admin` check before all three branches (addition, modification, deletion)
- Extracted `maybe_merge()` helper that gates on `is_admin`
- Admin path: posts "✅ Validated — merge manually when ready" comment, exits 0
- Non-admin path: unchanged (`gh pr merge --auto --squash`)

## Test plan
- [ ] Non-admin player PR → still auto-merges (existing behavior preserved)
- [ ] Admin player PR → CI passes, comment posted, no auto-merge

Co-authored-by: Claude Sonnet 4.6 <noreply@anthropic.com>

- Use GITHUB_TOKEN for admin PR comment in register job
  ([#42](https://github.com/after2400/liars-dice/pull/42),
  [`ce79351`](https://github.com/after2400/liars-dice/commit/ce79351e6a963e9bc8eeaac99c894e37a05a366c))

## Summary

- `LEADERBOARD_PAT` lacks `addComment` permission, causing the `register` job to fail with `GraphQL: Resource not accessible by personal access token (addComment)` when posting the admin manual-merge notice
- Add `pull-requests: write` to the `register` job's permissions so `GITHUB_TOKEN` can comment
- Pass `GITHUB_TOKEN` as `COMMENT_TOKEN`; scope it to just the `gh pr comment` call in `maybe_merge()`, keeping `GH_TOKEN=LEADERBOARD_PAT` for the privileged merge operation

## Test plan

- [x] Merge this PR (non-player, merges normally)
- [x] Rerun PR #41 CI — register job should post "✅ Validated. Admin player PR — merge manually when ready." without error

Co-authored-by: Claude Sonnet 4.6 <noreply@anthropic.com>

### 📖 Documentation

- Simulation procedure, CONTRIBUTING.md review and fixes
  ([#43](https://github.com/after2400/liars-dice/pull/43),
  [`b00c7a3`](https://github.com/after2400/liars-dice/commit/b00c7a3367302ebc7ee61ffea5645ef25c1fac6b))

Updates both `CLAUDE.md` and `CONTRIBUTING.md` with simulation docs and several fixes found during a consistency review.

**CLAUDE.md**
- Add **Local simulation** section: register a player locally, single-step sims, full quarter sim, cleanup

**CONTRIBUTING.md**
- Add full quarter sim (`uv run python -m game.simulation.quarter`) to the Simulating runs section
- Add PR rules callout: PRs must touch only `players/`, one file per PR, enforced by CI
- Add class name uniqueness requirement to the Adding a Player checklist
- Fix `bet_history` entry schema — `dice_count` field was missing
- Fix example dates throughout (July 7 and July 14 are Tuesdays, not Mondays)

---

---------

Co-authored-by: Claude Sonnet 4.6 <noreply@anthropic.com>

### 🏗 Chores

- **config**: Add player_tests/ sandbox and split pytest recipes
  ([#38](https://github.com/after2400/liars-dice/pull/38),
  [`626da7a`](https://github.com/after2400/liars-dice/commit/626da7a2b38de8c4b2f6a36eb1f1adad4134d3c5))

## Summary

- Adds `player_tests/` as a gitignored local sandbox for bot development — write tests freely, they never get committed
- `player_tests/.gitkeep` is tracked so the directory exists on fresh clones
- Splits test recipes: `just pytest` runs `player_tests/` only (community default); `just pytest-all` runs `tests/` + `examples/tests/` (engine/admin PRs)
- `pyproject.toml` testpaths simplified to `["player_tests"]`; recipes pass explicit paths so the two suites stay fully separate — matching the PR guard that enforces the same separation at commit time
- CLAUDE.md updated with new testing conventions and the `just pytest-all` requirement for engine PRs

## Test plan

- [x] `just pytest` exits 0 on empty `player_tests/` (no tests collected = not an error)
- [x] `just pytest-all` runs 159 engine tests, all passing

Co-authored-by: Claude Sonnet 4.6 <noreply@anthropic.com>

- **config**: Add pythonpath to pytest so player_tests can import game modules
  ([`bf02d37`](https://github.com/after2400/liars-dice/commit/bf02d37c145b366da333f557ea34ccb759b1ea53))

- **config**: Set worktree baseRef to fresh
  ([`7a08076`](https://github.com/after2400/liars-dice/commit/7a0807632a524fc96b0b24fc8988ab0074e968a4))

Prevents new worktrees from inheriting commits from the current session HEAD. Previously "head" caused feat+nuke-laloosh commits to be bundled into an unrelated PR.


## v1.3.0 (2026-06-16)

### ✨ Features

- **game**: Add dice_count to bet_history entries
  ([`0ebc0e6`](https://github.com/after2400/liars-dice/commit/0ebc0e6d7529851de60d360651669a9f81fe978e))

### 🔁 Continuous Integration

- Block mixed player/non-player PRs for all contributors
  ([`ba95496`](https://github.com/after2400/liars-dice/commit/ba95496d441c2aa61132ab1bc457b664f5c21af3))


## v1.2.0 (2026-06-15)

### ✨ Features

- **game**: Pass tier to algo as opt-in parameter
  ([#35](https://github.com/after2400/liars-dice/pull/35),
  [`7c12b36`](https://github.com/after2400/liars-dice/commit/7c12b369aab1d241125b4c58c2bab8b220185034))

## Summary

- Players can now declare `tier=None` in their `algo` signature to receive the current league tier (`"L1"`, `"CH"`, `"PRM"`) on every turn — enables per-tier strategy calibration (e.g. different opening aggression in CH vs PRM)
- Detection switches from position-count to parameter-name-based, making `stats` and `tier` fully independent opt-ins (no dummy param needed)
- Registration validates that any player declaring `tier` handles `None` gracefully — rejects at registration rather than crashing on tournament Mondays

## Test plan

- [x] `just pytest` passes (158 tests)
- [x] `test_tier_passed_to_tier_arg_player` — player receives correct tier string
- [x] `test_tier_none_when_not_specified` — player receives `None` when no tier given
- [x] `test_stats_and_tier_independent` — `stats`-only and `tier`-only players each get only what they declared
- [x] `test_tier_none_crash_fails_validation` — registration rejects a player that crashes on `tier=None`
- [x] `test_valid_player_with_tier_param` — well-behaved tier-aware player passes registration

Co-authored-by: Claude Sonnet 4.6 <noreply@anthropic.com>


## v1.1.0 (2026-06-15)

### ✨ Features

- Quarter simulation script and season_utils move into game package
  ([#34](https://github.com/after2400/liars-dice/pull/34),
  [`23362ef`](https://github.com/after2400/liars-dice/commit/23362efa9b989daa999b75b452b2b1f72a61a447))

## Summary

- Moves `season_utils.py` from `.github/scripts/` into `game/season/utils.py` so shared helpers are importable outside CI context
- Adds `game/simulation/quarter.py` — run a full quarter locally (`uv run python -m game.simulation.quarter`) with `DRY_RUN=true` to avoid GitHub side effects
- Updates `.github/scripts/reset_season.py` and `run_season.py` to import from the new `game.season.utils` location
- Adds 14 tests covering `compute_mondays`, `run_step`, `write_report`, and `parse_args`; all 153 tests pass

## Test Plan

- [x] `just pytest` — all 153 tests pass
- [x] `uv run python -m game.simulation.quarter --help` shows usage
- [x] `uv run python -m game.simulation.quarter --start 2026-07-06` runs a full Q3 2026 simulation, streams per-step output, writes `sim-Q3-2026.md`
- [x] `git checkout -- leaderboard.yaml` (or `just clean`) restores leaderboard after simulation

---------

Co-authored-by: Claude Sonnet 4.6 <noreply@anthropic.com>


## v1.0.2 (2026-06-15)

### 🐞 Bug Fixes

- Dry-run README guard, uv.lock PSR sync, and CLAUDE.md overhaul
  ([#33](https://github.com/after2400/liars-dice/pull/33),
  [`809e02b`](https://github.com/after2400/liars-dice/commit/809e02bd41ce09f3fd668dd985adf6b6f8175dd8))

## Summary

- **`fix(scripts)`** — `_update_readme()` now returns early when `DRY_RUN=1`, so `just simulate-season` no longer dirties `README.md`. Test added to verify.
- **`fix(workflows)`** — Release workflow now runs PSR in two passes (per the official uv integration guide): bump version without committing → sync `uv.lock` → full release commit + tag. Also one-time-syncs `uv.lock` which was stuck at `0.9.1`.
- **`docs`** — `CLAUDE.md` gains a **Repo overview** section (tiers, quarter cycle, leaderboard as source of truth, key env vars, key scripts), a **Commits** section (pointers to `.commitlintrc.mjs` for valid types/scopes and `pyproject.toml` for what triggers a version bump), and fixes `just pytest` usage throughout.

## Test plan

- [x] `just pytest` passes locally
- [x] `just simulate-season` no longer modifies `README.md` after the run
- [x] After merge, confirm the version in `uv.lock` matches `pyproject.toml` and doesn't change on `uv run`

---------

Co-authored-by: Claude Sonnet 4.6 <noreply@anthropic.com>

### 🏗 Chores

- Remove wrkflw from just develop ([#32](https://github.com/after2400/liars-dice/pull/32),
  [`1dbf96c`](https://github.com/after2400/liars-dice/commit/1dbf96ced55dbba4cf8cd79bd54b412a833da546))

## Summary

- Removes `uv tool install --upgrade wrkflw` from `just develop` — wrkflw is a macOS/Homebrew tool with no PyPI package, breaking `just develop` on fresh clones
- Adds a comment pointing maintainers to `brew install wrkflw` instead

## Test plan

- [x] `just develop` completes without error on a fresh clone

Co-authored-by: Claude Sonnet 4.6 <noreply@anthropic.com>


## v1.0.1 (2026-06-14)

### 🐞 Bug Fixes

- Lint on PRs only; release workflow_dispatch; platform-neutral pre-commit
  ([#30](https://github.com/after2400/liars-dice/pull/30),
  [`6c4b02e`](https://github.com/after2400/liars-dice/commit/6c4b02ee71edb49b0c97743f13f0a523f75c48af))

## Summary

- Removes `push: branches: [main]` from `lint.yml` — ruff and commitlint now run on PRs only, where they gate merges (including player auto-merges via `register-player.yml`)
- Adds `workflow_dispatch` to `release.yml` so PSR can be triggered manually when needed
- Deletes stale `Justfile` (`.Justfile` is the authoritative copy; both existed after the PR #28 squash)
- Switches commitlint pre-commit hook from `language: system` to `language: node` via `alessandrojcm/commitlint-pre-commit-hook` — pre-commit manages the Node environment automatically, making local setup platform-neutral
- Adds `pre-commit install --hook-type commit-msg && pre-commit install` to `just develop`

## Test plan

- [x] After merge, open a test PR and confirm `ruff` and `commitlint` checks appear and must pass before merge
- [x] Trigger `release.yml` manually via Actions → release → Run workflow and confirm PSR runs
- [x] `just develop` installs pre-commit hooks end-to-end on a clean clone

---------

Co-authored-by: Claude Sonnet 4.6 <noreply@anthropic.com>

### 📖 Documentation

- CONTRIBUTING.md, RULES.md, and PSR double-trigger fix
  ([#29](https://github.com/after2400/liars-dice/pull/29),
  [`64c125e`](https://github.com/after2400/liars-dice/commit/64c125e0f7534626ae1543262c07f186780c9f9e))

## Summary

- Creates \`CONTRIBUTING.md\` with Adding a Player, Player API, and Running Locally (expanded with \`just\` recipes)
- Creates \`RULES.md\` with the game rules
- Slims \`README.md\` — replaces the moved sections with a two-line hook near the top; updates Project Structure to reflect \`.Justfile\`, \`release.yml\`, \`reset_season.py\`, and \`season_utils.py\`
- Adds \`commit_message = "chore(release): v{version} [skip ci]"\` to PSR config so its automated commit doesn't re-trigger the release workflow or run lint/commitlint a second time
- Adds \`paths: ["players/**"]\` to \`register-player.yml\` so validate/register jobs only run on PRs that actually touch player files

## Test plan

- [x] \`README.md\` hook line links to \`CONTRIBUTING.md\` and \`RULES.md\`
- [x] \`CONTRIBUTING.md\` covers Adding a Player, Player API, and full local dev workflow including \`just\` recipes
- [x] After merge, the next PSR release commit carries \`[skip ci]\` and the release workflow fires only once
- [x] Docs-only PRs no longer trigger register/validate jobs

---------

Co-authored-by: Claude Sonnet 4.6 <noreply@anthropic.com>


## v1.0.0 (2026-06-14)

### ✨ Features

- PSR + just — automated releases and local dev recipes (v1.0.0)
  ([#28](https://github.com/after2400/liars-dice/pull/28),
  [`d036153`](https://github.com/after2400/liars-dice/commit/d0361534db2bde9c49ff9c4ac75d9ec5151a7ccd))

## Summary

- Extends \`season_utils.py\` with \`_today\`, \`current_quarter\`, \`is_tournament_monday\` (moved from \`reset_season.py\`) and new \`next_tournament_monday()\` — returns the first Monday on/after the next quarterly boundary
- Removes the three date functions from \`reset_season.py\`; imports them from \`season_utils\` instead
- Adds \`doh\` type to \`.commitlintrc.mjs\` — escape hatch that never bumps the version and never appears in the CHANGELOG
- Adds \`.Justfile\` at repo root with \`develop\`, \`pytest\`, \`lint\`, \`simulate-season\`, \`simulate-tournament\`, and \`clean\` recipes
- Adds \`.github/workflows/release.yml\` — PSR runs on every push to \`main\`, bumps version, regenerates CHANGELOG, creates GitHub Release automatically

## Test plan

- [x] \`uv run pytest -v\` passes (all 138 tests green, including 3 new \`next_tournament_monday\` tests)
- [x] \`just pytest\` runs the same suite via the Justfile
- [x] \`just simulate-tournament && just clean\` resolves the next tournament Monday, dry-runs it, and cleans up
- [x] After merge, the \`release\` workflow creates a v1.0.0 GitHub Release automatically

---------

Co-authored-by: Claude Sonnet 4.6 <noreply@anthropic.com>

### 🏗 Chores

- **release**: V0.9.1
  ([`51ab5bc`](https://github.com/after2400/liars-dice/commit/51ab5bc1360d6afac956ba758063940075467d8d))


## v0.9.1 (2026-06-14)

### 🐞 Bug Fixes

- **scripts**: Extract shared leaderboard I/O into season_utils
  ([#27](https://github.com/after2400/liars-dice/pull/27),
  [`46311a0`](https://github.com/after2400/liars-dice/commit/46311a061027a3aebfccdcb43186267e8821da12))

## Summary

- Creates `.github/scripts/season_utils.py` with shared `_load_lb` and `_save_lb`
- Removes duplicate `_load_lb` from `run_season.py` and both functions from `reset_season.py`
- Removes now-unused `import yaml` from both scripts (yaml only needed in season_utils now)
- Adds `tests/test_season_utils.py` with 6 tests covering load/save/round-trip behavior
- Updates `test_reset_season.py` loader to add `.github/scripts/` to `sys.path` (required for importlib-based loading to resolve sibling imports)

## Test plan

- [x] `uv run pytest -v` passes (135 tests green)
- [x] `_load_lb` and `_save_lb` no longer defined in `run_season.py` or `reset_season.py`
- [x] `season_utils.py` is the single source of truth for leaderboard I/O

---------

Co-authored-by: Claude Sonnet 4.6 <noreply@anthropic.com>

### 🏗 Chores

- Add .worktrees/ to .gitignore
  ([`b55d4cc`](https://github.com/after2400/liars-dice/commit/b55d4cc0cbfbb71c54dc88aa9fe7d25e3bf5ec6c))


## v0.9.0 (2026-06-13)

### ✨ Features

- Quarterly season structure with tournament reset
  ([#26](https://github.com/after2400/liars-dice/pull/26),
  [`4ebec93`](https://github.com/after2400/liars-dice/commit/4ebec93337456f6fdacf960a41d3bce2bfe90193))

## Summary

- Implements quarterly tournament reset pipeline (`reset_season.py`) — zeros all tier stats, forms S-curve seeded pools, runs games, assigns placements, creates season tracking issue
- Replaces `run-season.yml` with `run-monday.yml` — single workflow that branches on tournament Monday vs regular season run
- Adds `tier_capacities()` and `detect_entry_tier()` to leaderboard module; `register_player.py` now delegates to these
- Adds `--players` flag to game engine for running exact pool members
- Moves season tracking issue number from GitHub Actions var into `leaderboard.yaml` as `current_season_issue`
- Adds `TODAY` / `DRY_RUN` env vars for local testing with `wrkflw`
- Quotes player display names containing commas; strips control characters from all display names
- Adds `player:` commit type to commitlint; removes `players` scope (use `player:` for all player additions)

## Test plan

- [x] `uv run pytest -v` — 129 tests pass
- [x] `TODAY=2026-07-07 DRY_RUN=1 uv run python .github/scripts/reset_season.py` — tournament runs, leaderboard tiers reassigned, summary printed to stdout, no gh calls (no issue created/commented)
- [x] `DRY_RUN=1 uv run python .github/scripts/run_season.py` — season mode, no gh issue comment
- [x] `wrkflw validate .github/workflows/run-monday.yml` — passes
- [x] Commitlint rejects old scope, accepts new type (exit codes confirm):
  ```bash echo "feat(players): add Alice strategy" | npx commitlint; echo "exit: $?" # expect exit: 1 echo "player: add Alice strategy" | npx commitlint; echo "exit: $?" # expect exit: 0
  ```

---------

Co-authored-by: Claude Sonnet 4.6 <noreply@anthropic.com>


## v0.8.5 (2026-06-11)

### 🐞 Bug Fixes

- **leaderboard**: Rebalance CH→L1 by relegating Cleo
  ([#25](https://github.com/after2400/liars-dice/pull/25),
  [`959a9cb`](https://github.com/after2400/liars-dice/commit/959a9cb6b5e381c3017ace640b678cbe983e8581))

## Summary Data-only repair of the imbalance the cascade bug left behind (CH=5 / L1=2). Depends on #23 (stats fix) and #24 (relegation fix), both merged.

- **Move Cleo CH→L1** in `leaderboard.yaml` (`tier`, `tier_since`; `tier_stats` untouched). Cleo was the worst CH performer last run (0.4%); the corrected top-down settlement would have relegated her, with Remy protected as the parachutist from PRM. No games replayed.
- **Regenerate `README.md`** standings from the repaired leaderboard. This also picks up #23's fix — the "Games" column now shows total games across tiers (e.g. Eva: 1490 wins / 5000 games / 29.8%, previously a misleading 2000).

Result: PRM=4 / CH=4 / L1=3.

## Test Plan
- [x] Tier counts verified balanced after the move (PRM=4, CH=4, L1=3, inactive=0).
- [x] README regenerated via `_update_readme`; Cleo now in Level 1, Games column consistent with Total Wins / Win% Total.
- [x] `uv run pytest -v` — full suite green (88 passed); no code changed.

> Note: the Season Tracking workflow posts a **new** issue comment each run and never edits prior ones, so the last comment (2026-06-11) stays stale permanently. Corrected markdown to manually edit that comment will be provided separately.

Co-authored-by: Claude Opus 4.8 <noreply@anthropic.com>


## v0.8.4 (2026-06-11)

### 🐞 Bug Fixes

- **leaderboard**: Cascade relegations via top-down settlement
  ([#24](https://github.com/after2400/liars-dice/pull/24),
  [`0e1b0d7`](https://github.com/after2400/liars-dice/commit/0e1b0d7a346f640354229f098a72cbb90496ea33))

## Summary Fixes a relegation bug where the nightly season run could not cascade relegations, leaving the ladder imbalanced (e.g. CH=5 / L1=2).

**Root cause:** the season runs tiers bottom-up and applied relegations per-tier immediately. A relegation always lands in a tier that has
*already run*, so a tier decided its own relegations before it knew the tier above would push a player down into it. The PR #13 capacity guard then relegated no one when the tier looked exactly full.

**Fix:** split the two movements.
- **Promotions** stay in-pass (bottom-up, unchanged) in `apply_season_results` — a promoted player still plays the higher tier the same night.
- **Relegations** move to a single **top-down settlement pass** (`settle_relegations`) that runs once after all games, when every tier's real headcount is known. PRM's drop lands in CH before CH is settled, so the cascade completes in one pass.
- **Parachutist protection:** a player dropped *into* a tier this pass holds a protected seat and is not re-dropped a second division the same night; only players who actually *played* that tier are relegation candidates.

Also deletes superseded dead code (`apply_pending_relegation`, `update_leaderboard`, `detect_phase`).

Design + plan: `docs/specs/2026-06-11-relegation-cascade-settlement-design.md`, `docs/plans/2026-06-11-relegation-cascade-settlement.md`.

## Test Plan
- [x] Unit tests for `settle_relegations`: one-pass cascade, parachutist protection (isolated — fails if protection is removed), at-capacity no-op, L1→inactive only past TOP_N×2, disambiguated movement names.
- [x] `apply_season_results` no longer relegates (regression test).
- [x] End-to-end `test_run_season_rebalances_in_one_run`: fakes the game engine and asserts today's real scenario settles to PRM=4 / CH=4 / L1=3.
- [x] `uv run pytest -v` — full suite green (88 passed).

> Note: code-only change; it does not rewrite `leaderboard.yaml`. The current imbalance is repaired separately (follow-up C), and future runs settle correctly.

---------

Co-authored-by: Claude Opus 4.8 <noreply@anthropic.com>


## v0.8.3 (2026-06-11)

### 🐞 Bug Fixes

- **scripts**: Show total games in standings Games column
  ([#23](https://github.com/after2400/liars-dice/pull/23),
  [`21d13db`](https://github.com/after2400/liars-dice/commit/21d13db19a5c0108dcb869e8dc0148c7b50ed35b))

## Summary
- The `Games` column in `_standings_table` (`.github/scripts/run_season.py`) showed only the **current tier's** games (`ts.get('games', 0)`), while sitting in the "totals" group alongside `Win % Total` and `Total Wins` (both cumulative across tiers).
- This made the row internally inconsistent — e.g. Eva rendered `Total Wins=1490, Games=2000, Win% Total=29.8` (1490/2000 ≠ 29.8%), because her real total is 5000 games (2000 PRM + 3000 CH). `total_games` was already computed for the percentage but never displayed.
- Fix: the `Games` column now renders `total_games`. One-column change; fixes README standings, season summary, and the Season Tracking issue comment (all share `_standings_table`).

## Test Plan
- [x] Added `test_standings_games_column_shows_total_games_not_current_tier` (fails before, passes after).
- [x] `uv run pytest -v` — full suite green (102 passed).

Co-authored-by: Claude Opus 4.8 <noreply@anthropic.com>


## v0.8.2 (2026-06-11)

### 🏗 Chores

- **config**: Add specs and plans commit scopes
  ([#22](https://github.com/after2400/liars-dice/pull/22),
  [`4b2d832`](https://github.com/after2400/liars-dice/commit/4b2d832f6fdd74bfe9876e94984798c92452e2b8))

## Summary
- Add `specs` and `plans` to the commitlint `scope-enum` so documentation commits under `docs/specs/` and `docs/plans/` can use `docs(specs):` / `docs(plans):`.

These scopes mirror the existing directory layout; type stays `docs`, scope names the doc area.

## Test Plan
- [x] `git commit` with a `docs(specs):` / `docs(plans):` message passes the commitlint pre-commit hook (previously rejected by `scope-enum`).

Co-authored-by: Claude Opus 4.8 <noreply@anthropic.com>


## v0.8.1 (2026-06-11)

### ✨ Features

- **players**: Add Pyro (Liar², Pants on Fire)
  ([#19](https://github.com/after2400/liars-dice/pull/19),
  [`99231f1`](https://github.com/after2400/liars-dice/commit/99231f1e3cc590a0791020ec821922f12a276ce4))

## Summary

Adds **Pyro** ("Liar², Pants on Fire"), a basic roster-filler player. Plays like Topper — steps the prior bid up one notch in `(quantity, face)` order over faces 2–6 — but with a short fuse: she calls liar as soon as that step's quantity would exceed `total_dice/3`. Opens `⌊total_dice/3⌋` fives (break-even quantity, one face below Topper's sixes; clamped to ≥1).

One player file, per the register-player one-player-per-PR rule. Unit tests will be added separately.

## Test Plan

- [x] `uv run python -m game.validate players/pyro.py` — OK (20-char name passes the ≤25 limit, no parentheses)
- [x] Verified locally against Topper in earlier integration runs (hair-trigger behavior confirmed)

Co-authored-by: Claude Opus 4.8 <noreply@anthropic.com>

- **players**: Add Topper ([#18](https://github.com/after2400/liars-dice/pull/18),
  [`963217c`](https://github.com/after2400/liars-dice/commit/963217cd236083e91c6e183d9c7da0bff8e0c9fd))

## Summary

Adds **Topper**, a basic roster-filler player. Opens `⌊total_dice/3⌋` sixes (a break-even bid, clamped to ≥1), and otherwise steps the prior bid up one notch in `(quantity, face)` order over faces 2–6 — bump the face by 1, and once the face is 6, increment quantity and reset face to 2. Calls liar only when that step would need more dice than are in play.

One player file, per the register-player one-player-per-PR rule.

## Test Plan

- [x] `uv run pytest tests/test_topper.py -q` — 8 passed
- [x] `uv run python -m game.validate players/topper.py` — OK

---------

Co-authored-by: Claude Opus 4.8 <noreply@anthropic.com>

### 🐞 Bug Fixes

- **workflows**: Privilege-separate the player-registration jobs
  ([#21](https://github.com/after2400/liars-dice/pull/21),
  [`b2b9664`](https://github.com/after2400/liars-dice/commit/b2b9664b15040de15c901d0cdded27dac7ae74af))

## Summary Closes a privilege bug in `register-player.yml`: the **privileged `register` job** (which holds `LEADERBOARD_PAT`) imported the submitted player file via `register_player.py` (`spec.loader.exec_module`), so contributor-controlled code ran in a process whose environment contained the PAT.

- **Stop executing contributor code in the privileged job.** The `validate` job already performs every import-based check (`game.validate`: load, class-matches-filename, instantiation, `algo` callable, display-name rules) and gates `register` via `needs:`. The addition path now does only a read-only uniqueness check — new `lb_has_player.py` (case-insensitive class-name match against `leaderboard.yaml`, no import) — then merges.
- **Per-job least privilege.** Workflow-level `contents: write` / `pull-requests: write` (inherited by both jobs) is replaced with per-job blocks: `validate` → `contents: read` + `pull-requests: write`;

`register` → `contents: read`. So a `GITHUB_TOKEN` stolen from exec'd player code in `validate` can no longer push to `main`. Privileged merges still use the PAT.

No behavior change to registration: the real leaderboard write still happens in `update-leaderboard.yml` on push to `main` (trusted, post-merge content). `register_player.py` is unchanged.

Out of scope (noted in spec): the `register` job's `uv sync` runs against checked-out `pyproject.toml`, but that step holds no secret and non-player PRs are skipped.

Spec: `docs/specs/2026-06-11-register-job-privilege-separation-design.md` Plan: `docs/plans/2026-06-11-register-job-privilege-separation.md`

Companion (done outside this PR): `workflows: write` removed from the fine-grained `LEADERBOARD_PAT`, leaving it scoped to this repo with `contents` + `pull requests`.

## Test Plan
- [x] `uv run pytest` → 101 passed (96 + 5 new `lb_has_player` tests)
- [x] `register-player.yml` parses as YAML; no `register_player.py`/`exec_module` in the `register` job
- [x] per-job permissions verified programmatically
- [ ] End-to-end: owner opens a throwaway player PR after merge to confirm auto-merge still works

---------

Co-authored-by: Claude Opus 4.8 <noreply@anthropic.com>

### ✅ Testing

- **tests**: Add self-contained example player template
  ([#20](https://github.com/after2400/liars-dice/pull/20),
  [`e812f11`](https://github.com/after2400/liars-dice/commit/e812f1141732f9d84d49b52403ece635c104605a))

## Summary
- Adds `examples/players/example.py` (`class Example`) — a heavily-commented template that documents the full player contract (class-name-matches-filename, `name` rules, `algo` signature, return-`None`-to-call-liar, wilds, raise rules) in one place for new authors to copy.
- Adds `examples/tests/test_example.py` — a self-contained test that references **only** the example player, so it can't bit-rot against real players, but exercises the live game engine (`Bet`, `bet_validator`).
- Wires `examples/tests` into `testpaths` in `pyproject.toml` so the canonical `uv run pytest` collects it — the template is guaranteed to keep working.
- Updates `CLAUDE.md` to drop the explicit `tests/` path from the test command (otherwise the example tests are skipped).

Decoupled by design: only an admin can touch both `examples/players/` and `examples/tests/`, and neither references real player files, so there's no cross-bitrot and they serve as ready-made dev examples.

## Test Plan
- [x] `uv run pytest` → 96 passed (91 existing + 5 new example tests)
- [x] `uv run python -m game.validate examples/players/example.py` → OK
- [ ] Confirm CI green on the PR

Co-authored-by: Claude Opus 4.8 <noreply@anthropic.com>

### ♻️ Refactoring

- **tests**: Drop redundant per-function yaml imports
  ([#15](https://github.com/after2400/liars-dice/pull/15),
  [`b5c8aa6`](https://github.com/after2400/liars-dice/commit/b5c8aa67668b777b1c3005765a76f271eb34a50e))

## Summary

`tests/test_leaderboard.py` imports `yaml` at module level (line 1), but 9 test functions each redundantly re-imported it locally as `import yaml as _yaml` and then called `_yaml.dump` / `_yaml.safe_load`. This was copy-paste cruft — the module-level `yaml` is already in scope everywhere.

Removed all 9 local imports and pointed the call sites at the module-level `yaml`. No behavior change; pure tidy-up.

## Test Plan

- [x] `uv run pytest tests/ -q` — 89 passed
- [x] `uv run ruff check tests/test_leaderboard.py` — clean
- [x] `uv run ruff format --check tests/test_leaderboard.py` — formatted
- [x] No `_yaml` references remain

Co-authored-by: Claude Opus 4.8 <noreply@anthropic.com>

### 🏗 Chores

- **players**: Raise display-name limit to 25 and consolidate validation
  ([#16](https://github.com/after2400/liars-dice/pull/16),
  [`f078c7f`](https://github.com/after2400/liars-dice/commit/f078c7ff6f6ddff60f80a1579473f92c51c07b47))

## Summary

Two related changes to player display-name handling:

1. **Raise the limit 20 → 25 chars.** Gives authors more headroom (the old 20 was arbitrary). No functional breakage — names are plain strings and the standings tables auto-size their name column. 2. **Single source of truth for the name rules.** The limit previously lived in two places (`register_player.py`'s `MAX_NAME_LEN` and a hardcoded literal in `lb_update_name.py`), and `game.validate` — the player-validation entry point — didn't enforce the name at all. Now `MAX_NAME_LEN` + a `validate_display_name()` helper live in `game/validate.py`, and all three consumers (register, rename, validate) use it, so the length limit and the no-parentheses rule can't drift apart again.

## Test Plan

- [x] `uv run pytest tests/ -q` — 91 passed
- [x] `game.validate` now rejects over-limit / parenthesised names (new tests in `tests/test_validate_player.py`)
- [x] `register_player.py` rejection test updated to a 26-char name
- [x] README + scheduled-league spec docs updated to "≤ 25"

---------

Co-authored-by: Claude Opus 4.8 <noreply@anthropic.com>


## v0.8.0 (2026-06-10)

### ✨ Features

- **leaderboard**: Disambiguate duplicate player display names
  ([#14](https://github.com/after2400/liars-dice/pull/14),
  [`afc02b5`](https://github.com/after2400/liars-dice/commit/afc02b588fe46cd2a31d78cb6b752ecaaed369fd))

## Summary

Player display names are not uniqueness-constrained (the leaderboard is keyed by class name), so two authors can each ship a player named e.g. "Topper". Until now every renderer showed `display_name` alone, so duplicates were indistinguishable.

This adds **conditional** disambiguation, render-time only (no `leaderboard.yaml` schema change):

- New pure helper `build_display_names(players)` in `game/components/leaderboard.py` maps each class name to its render string.
- A name is suffixed **only when 2+ players share it**. The suffix is `(github_username)` when that username is non-empty **and** unique within the colliding group; otherwise it falls back to `(class_name)`, which is always unique. This covers empty usernames and same-author collisions with no ambiguous outcome.
- **Global collision scope** — a player renders identically in every table/message.
- Wired into all render paths: summary standings, README standings + inactive, inactive inline list, game-results table, and promotion/relegation movement messages.
- **No-op on current data** — all current display names are unique; a regression test asserts the helper adds no suffixes to the live `leaderboard.yaml`.

Design: `docs/specs/2026-06-10-duplicate-name-display-design.md`

Plan: `docs/plans/2026-06-10-duplicate-name-display.md`

## Test Plan

- [x] `uv run pytest tests/ -q` — 89 passed
- [x] 8 unit tests for `build_display_names` (distinct usernames / one empty / both empty / same author / mixed / unique / missing key)
- [x] `apply_season_results` movement message uses disambiguated name
- [x] Summary + README rendering disambiguate duplicates and leave unique names bare
- [x] Regression test: no-op on the current all-unique leaderboard

---------

Co-authored-by: Claude Opus 4.8 <noreply@anthropic.com>


## v0.7.1 (2026-06-10)

### 🐞 Bug Fixes

- **leaderboard**: Relegate only when remaining players exceed capacity
  ([#13](https://github.com/after2400/liars-dice/pull/13),
  [`c6fa198`](https://github.com/after2400/liars-dice/commit/c6fa19853d45daa5f65f0ffd5e204d728e00c175))

## Summary

**Bug fix** — `max(1, len(remaining) - capacity)` → `max(0, ...)` in `apply_season_results`. The old formula guaranteed at least 1 relegation even when a tier ran at exact capacity with no promotion from below. After the top player was promoted out, the remaining count was already below capacity and no one should have been relegated. Bruno was incorrectly sent to L1 in today's run; his tier is corrected in `leaderboard.yaml` and the README standings.

**Promoted/Relegated visibility** — movements were buried inside collapsed `<details>` blocks in issue comments and absent from CI stdout entirely. Now `apply_season_results` returns movements, `run_season` prints them immediately, and the summary writer places them below the collapsed block so they're always visible.

**Docs/config** — README updated for weekly scheduling cadence; N_GAMES fallback default corrected 250 → 1000; player list replaced with GitHub link; `stats.py` added to project structure.

## Root cause

CH had 4 players at capacity (Eva, Remy, Alice, Bruno). L1 was skipped (only Cleo). Eva won CH and promoted to PRM, leaving 3 remaining. `max(1, 3 − 4) = 1` — Bruno was kicked to L1 even though the tier was now under capacity.

## Test plan

- [ ] `uv run pytest tests/ -v` — all 78 tests pass
- [ ] Verify next season run leaves CH at 4 without spurious relegations when L1 is skipped
- [ ] Confirm CI log shows ` Promoted: X → PRM` / ` Relegated: Y → CH` lines
- [ ] Confirm issue comment shows movements below the collapsed game results

---------

Co-authored-by: Claude Sonnet 4.6 <noreply@anthropic.com>

### 🔁 Continuous Integration

- **workflows**: Smart season scheduling — weekly + player-change trigger
  ([#12](https://github.com/after2400/liars-dice/pull/12),
  [`9e024a9`](https://github.com/after2400/liars-dice/commit/9e024a9eb679790f8b09cccc0a3854b530c4c87d))

## Summary

- Replaces the naive daily cron with a two-job structure: a lightweight `guard` job runs first and decides whether the season actually executes
- Season runs on **Mondays** (weekly cadence) or when any `players/*.py` file was added or modified in the last 24h — covers both new players and algorithm updates
- `workflow_dispatch` always bypasses the guard
- Prevents redundant runs when multiple players merge the same day (unlike a per-PR trigger)

## Test plan

- [ ] Trigger `workflow_dispatch` — confirm guard outputs `run=true` and season runs
- [ ] On a non-Monday with no recent player changes — confirm `run-season` job is skipped
- [ ] Merge a player file change and confirm the next 9am UTC cron picks it up

Co-authored-by: Claude Sonnet 4.6 <noreply@anthropic.com>


## v0.7.0 (2026-06-09)

### ✨ Features

- **game**: Add GameStats incremental stats class and migrate O(n) players
  ([#11](https://github.com/after2400/liars-dice/pull/11),
  [`8060812`](https://github.com/after2400/liars-dice/commit/80608126e2b3ce0a2307befb7f871518903ccd09))

## Summary

- Adds `game/components/stats.py` with `GameStats`, an O(1)-per-update stats object passed as an optional 6th arg to `algo()`. Players opt in by declaring `stats=None` in their signature.
- Integrates `GameStats` into the engine (`series.py` instantiates it once per series; `script.py` inspects signatures and passes it to players that declare the 6th parameter).
- Migrates Eva, Zara, Sloane, and Remy to use `GameStats` instead of scanning `bet_history`/`outcomes` on every turn — eliminating 10+ O(n) scans that make the last games in a 1000-game series ~2,000× slower than the first.
- Documents the `stats` parameter in the Player API section of README with a performance callout.

## Stats provided

| Attribute | Description | |-----------|-------------| | `bluff_rate` | Laplace-smoothed bluff fraction per player | | `raw_bluff_rate` | Unsmoothed `failed/(failed+held)` — used by Eva and Sloane for exact equivalence with their prior scan-based helpers | | `bluff_rate_by_face` / `raw_bluff_rate_by_face` | Same, per face | | `challenge_rate` / `challenge_success_rate` | Challenge behavior per player | | `face_bias`, `bid_increment`, `opening_aggression` | Bid tendency stats | | `mean_held_quantity_by_face` | Mean quantity of held bids per player per face | | `revealed_hand_frequency` / `rounds_with_hand` | Per-player dice density from revealed hands | | `current_round_velocity` | Avg quantity jump per bid step in current round |

## Equivalence guarantee

Eva and Sloane use `raw_bluff_rate` / `raw_bluff_rate_by_face` (unsmoothed) to exactly match their prior scan-based computations. Zara and Remy already used Laplace smoothing in their scan helpers, so they use the smoothed `bluff_rate`. `tests/test_player_stats_equivalence.py` verifies intermediate values and decisions match between the scan-path and stats-path for both players.

## Test plan

- [x] `uv run pytest tests/test_stats.py -v` — 17 tests covering all `GameStats` update logic
- [x] `uv run pytest tests/test_player_stats_equivalence.py -v` — 4 equivalence tests for Eva and Sloane
- [x] `uv run pytest tests/ -v` — 77 tests, all passing

---------

Co-authored-by: Claude Sonnet 4.6 <noreply@anthropic.com>


## v0.6.0 (2026-06-09)

### ✨ Features

- **scripts**: Redesign season summary with final standings + collapsed results
  ([`fe77de6`](https://github.com/after2400/liars-dice/commit/fe77de6de38442c864f7f14bc28f7f0105e7d8e2))

Replace per-tier cumulative tables with two sections:
- Final Standings: post-run tier assignments mirroring the README
- Game Results: collapsed details per tier with this-run wins/win%
  and promotion/relegation notes

Players no longer appear in their pre-relegation tier. Also updates README timezone copy from 4am EST to 9am UTC.

### 🐞 Bug Fixes

- **leaderboard**: Relegate only when tier ran at or above capacity
  ([`1430b77`](https://github.com/after2400/liars-dice/commit/1430b778bac46a9045ae8902df84ccf8cbd01e31))

The previous max(1, ...) fix always relegated at least 1 player even when a tier was well below capacity. This caused a collapse spiral: L1 with 2 players (capacity 8) would promote 1 then relegate the other to inactive, shrinking the league unnecessarily.

New rule: relegate if the tier *started* at or above capacity (always at least 1, enforcing competitive pressure on full cohorts). Thin tiers below capacity are left to grow naturally via incoming promotions.

Also removes the dead if/else branch where both arms were identical. Adds test covering the thin-tier no-relegation case.

- **workflows**: Pull --rebase before push in season commit step
  ([`f255b62`](https://github.com/after2400/liars-dice/commit/f255b62af4ffa1ae18262ca9535763b3c944b733))

Prevents rejection when commits land on main during the multi-minute season script run.


## v0.5.0 (2026-06-09)

### ✨ Features

- **game**: Expand standings columns with per-division and total win stats
  ([`a747678`](https://github.com/after2400/liars-dice/commit/a747678df8a8fc2b0462809680ce36f0c75668e7))

### 🐞 Bug Fixes

- **game**: Always relegate bottom player when tier runs; add All Wins column to standings
  ([`b5bdd49`](https://github.com/after2400/liars-dice/commit/b5bdd498020b9e304a476d5d9e6010662f450b31))

- **leaderboard**: Register Eva, Sloane, Zara, Remy in CH
  ([`91ae557`](https://github.com/after2400/liars-dice/commit/91ae557d42adf322114e99a8c428c8959f59f020))

- **leaderboard**: Reset to pre-new-players state
  ([`df0ba50`](https://github.com/after2400/liars-dice/commit/df0ba509a3821e075ec5c8b59167a5448a92bfef))

- **workflows**: Delete PR source branch after leaderboard update
  ([`5fd78d7`](https://github.com/after2400/liars-dice/commit/5fd78d7f864ac374ede6c83503adbc8e65088ffb))

- **workflows**: Use LEADERBOARD_PAT for protected branch pushes and merges
  ([`8767faa`](https://github.com/after2400/liars-dice/commit/8767faa82e4d0d22bc8c755f58659beba62966c9))


## v0.4.1 (2026-06-09)

### 🐞 Bug Fixes

- Post-merge improvements — validate module, CI guard, no-tier run, local dev docs
  ([`07b0afa`](https://github.com/after2400/liars-dice/commit/07b0afae7be5a9519c91f42404f9f329162bc510))

- Move validate_player.py into game.validate package; invoke as `python -m game.validate`
- Add --no-game-results flag to suppress per-game output in local runs
- Add validate CI job to register-player workflow (runs before register, rejects bad player files)
- Add 30-minute timeout to run-season job
- Fix no-tier run to include all players in directory, not just leaderboard-registered ones
- Fix README season tracking link (#4)
- Clean up commitlint scope-enum; add workflows scope

- **workflows**: Move leaderboard commit to post-merge
  ([#8](https://github.com/after2400/liars-dice/pull/8),
  [`3b7b12e`](https://github.com/after2400/liars-dice/commit/3b7b12e88bee86003ee1a6dd71dc647d61059909))

## Problem

The `register` job committed the leaderboard update directly to the player's PR branch, then called `gh pr merge --auto --squash`. This advanced the branch HEAD beyond the commit that `validate` and `register` ran against — so GitHub's required status checks never matched the current HEAD, leaving every player PR permanently blocked.

## Fix

- **`register-player.yml`**: strip the leaderboard commit entirely. Pre-merge now only validates (using a temp copy of the leaderboard for additions) and calls `gh pr merge --auto --squash`. The branch HEAD never changes after checks run.
- **`update-leaderboard.yml`** (new): triggers on `push` to `main` when `players/*.py` changes. Detects added/modified/deleted files, runs the appropriate script, and commits the leaderboard update directly to `main`.

## Result

Player PR flow: 1. `validate` and `register` jobs run — branch HEAD unchanged 2. Required checks pass against the correct HEAD → auto-merge fires 3. Post-merge `update-leaderboard` workflow runs on `main`, commits leaderboard update with `[skip ci]`


## v0.4.0 (2026-06-09)

### ✨ Features

- Scheduled league redesign ([#5](https://github.com/after2400/liars-dice/pull/5),
  [`168b29d`](https://github.com/after2400/liars-dice/commit/168b29d7f17bfc4a83694aa205f7f17a1a18256a))

## Summary

- Replaces the per-PR game model with two decoupled workflows: `register-player.yml` (PR validation + auto-merge) and `run-season.yml` (daily scheduled season runner)
- Adds a tiered league structure (Premier / Championship / Level 1 / inactive) with bottom-up promotion/relegation applied within each daily run
- README auto-updates standings after each daily run; inactive division always collapsed; prettier suppressed on the leaderboard block

## Key changes

- `.github/workflows/register-player.yml` — validates player PRs, detects entry tier, commits leaderboard update, auto-merges
- `.github/workflows/run-season.yml` — daily cron, runs tiers bottom-up, commits leaderboard + README, posts summary to tracking issue (#4)
- `.github/scripts/run_season.py` — season driver with `apply_season_results()` applied between tiers
- `.github/scripts/register_player.py` — player validation and leaderboard registration
- Helper scripts: `lb_owner.py`, `lb_delete.py`, `lb_update_name.py`
- `game/__main__.py` — added `--tier inactive` support; each tier now selects exactly its own players
- `leaderboard.yaml` schema updated with `tier_stats`, `tier_since`, `times_inactive`
- `.prettierignore` added for `leaderboard.yaml` and `season_summary.md`

## Test plan

- [x] `uv run pytest tests/ -v` passes (46 tests)
- [x] Register a player via PR to `players/` — workflow validates, updates leaderboard, auto-merges *(post-merge)*
- [x] Trigger `run-season.yml` via `workflow_dispatch` — confirm leaderboard and README update, summary posted to #4 *(post-merge)*
- [x] Set repo variables `N_GAMES`, `TOP_N`, `SEASON_TRACKING_ISSUE=4` before first scheduled run

Co-authored-by: Chuck Lunskis <cl@after2400.com>


## v0.3.0 (2026-06-08)

### ✨ Features

- Add CODEOWNERS and non-player file guard workflow
  ([#3](https://github.com/after2400/liars-dice/pull/3),
  [`69e7cf5`](https://github.com/after2400/liars-dice/commit/69e7cf5f378dc38c3f5dc01660dd6235b9dafd5e))

- Add CODEOWNERS and non-player file guard workflow
  ([#3](https://github.com/after2400/liars-dice/pull/3),
  [`69e7cf5`](https://github.com/after2400/liars-dice/commit/69e7cf5f378dc38c3f5dc01660dd6235b9dafd5e))

Restricts repository writes so non-admins can only contribute to players/. CODEOWNERS requires owner review for all other files; guard-non-player-prs.yml rejects PRs from non-admins that touch anything outside players/ before they can be merged.

---------

Co-authored-by: Claude Sonnet 4.6 <noreply@anthropic.com>

### 📖 Documentation

- Add player deletion rules, admin permission, batch delete
  ([#3](https://github.com/after2400/liars-dice/pull/3),
  [`69e7cf5`](https://github.com/after2400/liars-dice/commit/69e7cf5f378dc38c3f5dc01660dd6235b9dafd5e))

- Lock in schedule and churn rate decisions ([#3](https://github.com/after2400/liars-dice/pull/3),
  [`69e7cf5`](https://github.com/after2400/liars-dice/commit/69e7cf5f378dc38c3f5dc01660dd6235b9dafd5e))

- New players enter L1 minimum, never inactive
  ([#3](https://github.com/after2400/liars-dice/pull/3),
  [`69e7cf5`](https://github.com/after2400/liars-dice/commit/69e7cf5f378dc38c3f5dc01660dd6235b9dafd5e))

- Spec for scheduled league redesign ([#3](https://github.com/after2400/liars-dice/pull/3),
  [`69e7cf5`](https://github.com/after2400/liars-dice/commit/69e7cf5f378dc38c3f5dc01660dd6235b9dafd5e))

- Update spec with player naming, leaderboard schema, PR validation, inactive tier
  ([#3](https://github.com/after2400/liars-dice/pull/3),
  [`69e7cf5`](https://github.com/after2400/liars-dice/commit/69e7cf5f378dc38c3f5dc01660dd6235b9dafd5e))


## v0.2.0 (2026-06-08)

### ✨ Features

- Add Finn player (adaptive threshold strategy)
  ([`53cd56e`](https://github.com/after2400/liars-dice/commit/53cd56e7f773776f2c1345763fadc18838126d53))

### 🐞 Bug Fixes

- Add PYTHONPATH=. so workflow scripts can import game module
  ([`5645d2e`](https://github.com/after2400/liars-dice/commit/5645d2e53f66a2e0c0eae852857475845df6979b))

- Collapse python3 -c check to single line to fix YAML syntax error
  ([`631caa7`](https://github.com/after2400/liars-dice/commit/631caa7f3a47aab8b422862f343a36a324c27c9a))

Multi-line content at zero indentation inside a run: | block broke the YAML literal block scalar parser on GitHub.

- Correct detect_phase boundary, add PRM overflow cascade, repair leaderboard
  ([`3275477`](https://github.com/after2400/liars-dice/commit/3275477220727846d654ebb9cc98cf850a5154bf))

detect_phase used `total < top_n` (strict), so with exactly 4 players and TOP_N=4 it returned phase 2 (challenger_tier=CH). No CH players existed yet, so the game ran with only the new challenger — who trivially won all 250 games.

Fixes:
- detect_phase: `total < top_n` → `total <= top_n` so a full-but-not-overflowing
  PRM still accepts the next entrant directly (phase 1)
- evaluate.py: when phase-1 challenger enters and PRM is at capacity, relegate
  the last-place PRM player to CH (deferred) so the tier doesn't grow unbounded
- leaderboard.yaml: replace the impossible 250/250 Finn entry with real results
  from a 250-game run of all 5 players; Cleo (last place) gets pending CH relegation
- tests: add regression test for total == top_n → phase 1

- Per-tier stat tracking and solo-game guard
  ([`164a8cd`](https://github.com/after2400/liars-dice/commit/164a8cdf56ba921e57e32c5a250ade1d93533642))

- game/__main__.py: exit cleanly if fewer than 2 players in a tier,
  preventing trivial 100% win-rate from solo games
- leaderboard.py: replace flat total_wins/total_games/win_pct with
  tier_stats: {PRM: {wins, games, win_pct}} so performance in each
  tier is tracked independently
- evaluate.py: ranked() tiebreak uses tier-specific games; PR comment
  table shows tier-specific win% and game count
- tests: update fixtures and assertions to new schema
- leaderboard.yaml: reset to main's 4-player state with correct
  per-tier stats so CI can run a clean game 3 for Finn's entry

- Reset leaderboard to pre-Finn state so CI can run correctly
  ([`bab0693`](https://github.com/after2400/liars-dice/commit/bab0693bb192ce22585e1b7b8c6f7f97a0479d84))

The previous fix mistakenly put Finn into leaderboard.yaml on this branch. With 5 registered players, detect_phase returned 2 (CH) on every CI re-run, causing solo games (Cleo then Bruno winning trivially).

Resetting to 4-player main state: detect_phase now returns 1 (total=4 <= top_n=4), so the entry game plays all 5 players correctly.

- Restore leaderboard to clean state from first correct CI run
  ([`f7bf5ed`](https://github.com/after2400/liars-dice/commit/f7bf5ed34628aa194312592b12b781b33d247072))

Subsequent CI runs (before the already_registered guard landed) replayed the phase-2 solo-game bug again. Restoring to c07ee69 which had the correct 5-player PRM game results: Finn 24%, Cleo last (pending CH).

- Skip duplicate PRM section in PR comment for phase-1 entry
  ([`7aeada2`](https://github.com/after2400/liars-dice/commit/7aeada24152b82e39752c13d4ce1f49d4185a243))

When challenger_tier is PRM, entry_prefix is already "prm", so the hardcoded "prm" entry in the comment loop was including the same output file twice. Only add the secondary "prm" section when the entry game ran as CH.

- Skip game run if challenger is already registered in leaderboard
  ([`586dab8`](https://github.com/after2400/liars-dice/commit/586dab88b5c5e3c49f6dbf369a8e806b20e40572))

Every push to the PR branch triggered CI because finn.py was always new vs main. After the first successful run, Finn was in the leaderboard and subsequent CI runs produced bogus solo games.

The setup step now detects if the challenger player is already registered and exits early (already_registered=true). run-entry skips on that flag, and evaluate skips because run-entry result != 'success'.


## v0.1.0 (2026-06-08)

- Initial Release
