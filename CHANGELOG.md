# CHANGELOG


## v1.4.3 (2026-06-17)

### Bug Fixes

- **ci**: Support fork PRs — switch register-player to pull_request_target
  ([#55](https://github.com/after2400/liars-dice/pull/55),
  [`00612b0`](https://github.com/after2400/liars-dice/commit/00612b0530f985432ac43d638adee363c333282c))

### Documentation

- Rename Run Monday → Run Season, add attribution, fix pytest docs
  ([#54](https://github.com/after2400/liars-dice/pull/54),
  [`181f518`](https://github.com/after2400/liars-dice/commit/181f5187c2b9209b2d6da3f4e721aa418121435d))


## v1.4.2 (2026-06-16)

### Bug Fixes

- **workflows**: Run daily and pick up new players since last run
  ([#49](https://github.com/after2400/liars-dice/pull/49),
  [`229d856`](https://github.com/after2400/liars-dice/commit/229d856518234895f8a97546acf2532af0594a8b))


## v1.4.1 (2026-06-16)

### Bug Fixes

- **workflows**: Dispatch season run when new player added on non-Monday
  ([#47](https://github.com/after2400/liars-dice/pull/47),
  [`6379e22`](https://github.com/after2400/liars-dice/commit/6379e228ddcda030e90a43ffebc4619b5fb85381))


## v1.4.0 (2026-06-16)

### Chores

- **config**: Add player_tests/ sandbox and split pytest recipes
  ([#38](https://github.com/after2400/liars-dice/pull/38),
  [`626da7a`](https://github.com/after2400/liars-dice/commit/626da7a2b38de8c4b2f6a36eb1f1adad4134d3c5))

- **config**: Add pythonpath to pytest so player_tests can import game modules
  ([`bf02d37`](https://github.com/after2400/liars-dice/commit/bf02d37c145b366da333f557ea34ccb759b1ea53))

- **config**: Set worktree baseRef to fresh
  ([`7a08076`](https://github.com/after2400/liars-dice/commit/7a0807632a524fc96b0b24fc8988ab0074e968a4))

### Continuous Integration

- Skip auto-merge for admin player PRs ([#40](https://github.com/after2400/liars-dice/pull/40),
  [`c4fda4d`](https://github.com/after2400/liars-dice/commit/c4fda4de6ca9abf3e90b5fb8ec9fc355c5841f60))

- Use GITHUB_TOKEN for admin PR comment in register job
  ([#42](https://github.com/after2400/liars-dice/pull/42),
  [`ce79351`](https://github.com/after2400/liars-dice/commit/ce79351e6a963e9bc8eeaac99c894e37a05a366c))

### Documentation

- Simulation procedure, CONTRIBUTING.md review and fixes
  ([#43](https://github.com/after2400/liars-dice/pull/43),
  [`b00c7a3`](https://github.com/after2400/liars-dice/commit/b00c7a3367302ebc7ee61ffea5645ef25c1fac6b))

### Features

- Deduplicate player display names in-game when they collide
  ([#45](https://github.com/after2400/liars-dice/pull/45),
  [`0cd15e2`](https://github.com/after2400/liars-dice/commit/0cd15e25dba43c44fabb2a31733c2aaf1a344576))


## v1.3.0 (2026-06-16)

### Continuous Integration

- Block mixed player/non-player PRs for all contributors
  ([`ba95496`](https://github.com/after2400/liars-dice/commit/ba95496d441c2aa61132ab1bc457b664f5c21af3))

### Features

- **game**: Add dice_count to bet_history entries
  ([`0ebc0e6`](https://github.com/after2400/liars-dice/commit/0ebc0e6d7529851de60d360651669a9f81fe978e))


## v1.2.0 (2026-06-15)

### Features

- **game**: Pass tier to algo as opt-in parameter
  ([#35](https://github.com/after2400/liars-dice/pull/35),
  [`7c12b36`](https://github.com/after2400/liars-dice/commit/7c12b369aab1d241125b4c58c2bab8b220185034))


## v1.1.0 (2026-06-15)

### Features

- Quarter simulation script and season_utils move into game package
  ([#34](https://github.com/after2400/liars-dice/pull/34),
  [`23362ef`](https://github.com/after2400/liars-dice/commit/23362efa9b989daa999b75b452b2b1f72a61a447))


## v1.0.2 (2026-06-15)

### Bug Fixes

- Dry-run README guard, uv.lock PSR sync, and CLAUDE.md overhaul
  ([#33](https://github.com/after2400/liars-dice/pull/33),
  [`809e02b`](https://github.com/after2400/liars-dice/commit/809e02bd41ce09f3fd668dd985adf6b6f8175dd8))

### Chores

- Remove wrkflw from just develop ([#32](https://github.com/after2400/liars-dice/pull/32),
  [`1dbf96c`](https://github.com/after2400/liars-dice/commit/1dbf96ced55dbba4cf8cd79bd54b412a833da546))


## v1.0.1 (2026-06-14)

### Bug Fixes

- Lint on PRs only; release workflow_dispatch; platform-neutral pre-commit
  ([#30](https://github.com/after2400/liars-dice/pull/30),
  [`6c4b02e`](https://github.com/after2400/liars-dice/commit/6c4b02ee71edb49b0c97743f13f0a523f75c48af))

### Documentation

- CONTRIBUTING.md, RULES.md, and PSR double-trigger fix
  ([#29](https://github.com/after2400/liars-dice/pull/29),
  [`64c125e`](https://github.com/after2400/liars-dice/commit/64c125e0f7534626ae1543262c07f186780c9f9e))


## v1.0.0 (2026-06-14)

### Chores

- **release**: V0.9.1
  ([`51ab5bc`](https://github.com/after2400/liars-dice/commit/51ab5bc1360d6afac956ba758063940075467d8d))

### Features

- PSR + just — automated releases and local dev recipes (v1.0.0)
  ([#28](https://github.com/after2400/liars-dice/pull/28),
  [`d036153`](https://github.com/after2400/liars-dice/commit/d0361534db2bde9c49ff9c4ac75d9ec5151a7ccd))


## v0.9.1 (2026-06-14)

### Bug Fixes

- **scripts**: Extract shared leaderboard I/O into season_utils
  ([#27](https://github.com/after2400/liars-dice/pull/27),
  [`46311a0`](https://github.com/after2400/liars-dice/commit/46311a061027a3aebfccdcb43186267e8821da12))

### Chores

- Add .worktrees/ to .gitignore
  ([`b55d4cc`](https://github.com/after2400/liars-dice/commit/b55d4cc0cbfbb71c54dc88aa9fe7d25e3bf5ec6c))


## v0.9.0 (2026-06-13)

### Features

- Quarterly season structure with tournament reset
  ([#26](https://github.com/after2400/liars-dice/pull/26),
  [`4ebec93`](https://github.com/after2400/liars-dice/commit/4ebec93337456f6fdacf960a41d3bce2bfe90193))


## v0.8.5 (2026-06-11)

### Bug Fixes

- **leaderboard**: Rebalance CH→L1 by relegating Cleo
  ([#25](https://github.com/after2400/liars-dice/pull/25),
  [`959a9cb`](https://github.com/after2400/liars-dice/commit/959a9cb6b5e381c3017ace640b678cbe983e8581))


## v0.8.4 (2026-06-11)

### Bug Fixes

- **leaderboard**: Cascade relegations via top-down settlement
  ([#24](https://github.com/after2400/liars-dice/pull/24),
  [`0e1b0d7`](https://github.com/after2400/liars-dice/commit/0e1b0d7a346f640354229f098a72cbb90496ea33))


## v0.8.3 (2026-06-11)

### Bug Fixes

- **scripts**: Show total games in standings Games column
  ([#23](https://github.com/after2400/liars-dice/pull/23),
  [`21d13db`](https://github.com/after2400/liars-dice/commit/21d13db19a5c0108dcb869e8dc0148c7b50ed35b))


## v0.8.2 (2026-06-11)

### Chores

- **config**: Add specs and plans commit scopes
  ([#22](https://github.com/after2400/liars-dice/pull/22),
  [`4b2d832`](https://github.com/after2400/liars-dice/commit/4b2d832f6fdd74bfe9876e94984798c92452e2b8))


## v0.8.1 (2026-06-11)

### Bug Fixes

- **workflows**: Privilege-separate the player-registration jobs
  ([#21](https://github.com/after2400/liars-dice/pull/21),
  [`b2b9664`](https://github.com/after2400/liars-dice/commit/b2b9664b15040de15c901d0cdded27dac7ae74af))

### Chores

- **players**: Raise display-name limit to 25 and consolidate validation
  ([#16](https://github.com/after2400/liars-dice/pull/16),
  [`f078c7f`](https://github.com/after2400/liars-dice/commit/f078c7ff6f6ddff60f80a1579473f92c51c07b47))

### Features

- **players**: Add Pyro (Liar², Pants on Fire)
  ([#19](https://github.com/after2400/liars-dice/pull/19),
  [`99231f1`](https://github.com/after2400/liars-dice/commit/99231f1e3cc590a0791020ec821922f12a276ce4))

- **players**: Add Topper ([#18](https://github.com/after2400/liars-dice/pull/18),
  [`963217c`](https://github.com/after2400/liars-dice/commit/963217cd236083e91c6e183d9c7da0bff8e0c9fd))

### Refactoring

- **tests**: Drop redundant per-function yaml imports
  ([#15](https://github.com/after2400/liars-dice/pull/15),
  [`b5c8aa6`](https://github.com/after2400/liars-dice/commit/b5c8aa67668b777b1c3005765a76f271eb34a50e))

### Testing

- **tests**: Add self-contained example player template
  ([#20](https://github.com/after2400/liars-dice/pull/20),
  [`e812f11`](https://github.com/after2400/liars-dice/commit/e812f1141732f9d84d49b52403ece635c104605a))


## v0.8.0 (2026-06-10)

### Features

- **leaderboard**: Disambiguate duplicate player display names
  ([#14](https://github.com/after2400/liars-dice/pull/14),
  [`afc02b5`](https://github.com/after2400/liars-dice/commit/afc02b588fe46cd2a31d78cb6b752ecaaed369fd))


## v0.7.1 (2026-06-10)

### Bug Fixes

- **leaderboard**: Relegate only when remaining players exceed capacity
  ([#13](https://github.com/after2400/liars-dice/pull/13),
  [`c6fa198`](https://github.com/after2400/liars-dice/commit/c6fa19853d45daa5f65f0ffd5e204d728e00c175))

### Continuous Integration

- **workflows**: Smart season scheduling — weekly + player-change trigger
  ([#12](https://github.com/after2400/liars-dice/pull/12),
  [`9e024a9`](https://github.com/after2400/liars-dice/commit/9e024a9eb679790f8b09cccc0a3854b530c4c87d))


## v0.7.0 (2026-06-09)

### Features

- **game**: Add GameStats incremental stats class and migrate O(n) players
  ([#11](https://github.com/after2400/liars-dice/pull/11),
  [`8060812`](https://github.com/after2400/liars-dice/commit/80608126e2b3ce0a2307befb7f871518903ccd09))


## v0.6.0 (2026-06-09)

### Bug Fixes

- **leaderboard**: Relegate only when tier ran at or above capacity
  ([`1430b77`](https://github.com/after2400/liars-dice/commit/1430b778bac46a9045ae8902df84ccf8cbd01e31))

- **workflows**: Pull --rebase before push in season commit step
  ([`f255b62`](https://github.com/after2400/liars-dice/commit/f255b62af4ffa1ae18262ca9535763b3c944b733))

### Features

- **scripts**: Redesign season summary with final standings + collapsed results
  ([`fe77de6`](https://github.com/after2400/liars-dice/commit/fe77de6de38442c864f7f14bc28f7f0105e7d8e2))


## v0.5.0 (2026-06-09)

### Bug Fixes

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

### Features

- **game**: Expand standings columns with per-division and total win stats
  ([`a747678`](https://github.com/after2400/liars-dice/commit/a747678df8a8fc2b0462809680ce36f0c75668e7))


## v0.4.1 (2026-06-09)

### Bug Fixes

- Post-merge improvements — validate module, CI guard, no-tier run, local dev docs
  ([`07b0afa`](https://github.com/after2400/liars-dice/commit/07b0afae7be5a9519c91f42404f9f329162bc510))

- **workflows**: Move leaderboard commit to post-merge
  ([#8](https://github.com/after2400/liars-dice/pull/8),
  [`3b7b12e`](https://github.com/after2400/liars-dice/commit/3b7b12e88bee86003ee1a6dd71dc647d61059909))


## v0.4.0 (2026-06-09)

### Features

- Scheduled league redesign ([#5](https://github.com/after2400/liars-dice/pull/5),
  [`168b29d`](https://github.com/after2400/liars-dice/commit/168b29d7f17bfc4a83694aa205f7f17a1a18256a))


## v0.3.0 (2026-06-08)

### Documentation

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

### Features

- Add CODEOWNERS and non-player file guard workflow
  ([#3](https://github.com/after2400/liars-dice/pull/3),
  [`69e7cf5`](https://github.com/after2400/liars-dice/commit/69e7cf5f378dc38c3f5dc01660dd6235b9dafd5e))


## v0.2.0 (2026-06-08)

### Bug Fixes

- Add PYTHONPATH=. so workflow scripts can import game module
  ([`5645d2e`](https://github.com/after2400/liars-dice/commit/5645d2e53f66a2e0c0eae852857475845df6979b))

- Collapse python3 -c check to single line to fix YAML syntax error
  ([`631caa7`](https://github.com/after2400/liars-dice/commit/631caa7f3a47aab8b422862f343a36a324c27c9a))

- Correct detect_phase boundary, add PRM overflow cascade, repair leaderboard
  ([`3275477`](https://github.com/after2400/liars-dice/commit/3275477220727846d654ebb9cc98cf850a5154bf))

- Per-tier stat tracking and solo-game guard
  ([`164a8cd`](https://github.com/after2400/liars-dice/commit/164a8cdf56ba921e57e32c5a250ade1d93533642))

- Reset leaderboard to pre-Finn state so CI can run correctly
  ([`bab0693`](https://github.com/after2400/liars-dice/commit/bab0693bb192ce22585e1b7b8c6f7f97a0479d84))

- Restore leaderboard to clean state from first correct CI run
  ([`f7bf5ed`](https://github.com/after2400/liars-dice/commit/f7bf5ed34628aa194312592b12b781b33d247072))

- Skip duplicate PRM section in PR comment for phase-1 entry
  ([`7aeada2`](https://github.com/after2400/liars-dice/commit/7aeada24152b82e39752c13d4ce1f49d4185a243))

- Skip game run if challenger is already registered in leaderboard
  ([`586dab8`](https://github.com/after2400/liars-dice/commit/586dab88b5c5e3c49f6dbf369a8e806b20e40572))

### Features

- Add Finn player (adaptive threshold strategy)
  ([`53cd56e`](https://github.com/after2400/liars-dice/commit/53cd56e7f773776f2c1345763fadc18838126d53))


## v0.1.0 (2026-06-08)

- Initial Release
