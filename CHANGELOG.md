# CHANGELOG


## v2.4.0 (2026-06-30)

### Continuous Integration

- Upgrade actions to node24 runtimes ([#137](https://github.com/after2400/liars-dice/pull/137),
  [`ecc3e32`](https://github.com/after2400/liars-dice/commit/ecc3e32ede2729df193a44fe6e5c77f964a0e854))

### Features

- **game**: Split PlayerStatsPanel into focusable sub-panels with clipboard copy
  ([#144](https://github.com/after2400/liars-dice/pull/144),
  [`af3dadd`](https://github.com/after2400/liars-dice/commit/af3dadd03621ad17cf854ef828f3d878e31814af))


## v2.3.0 (2026-06-30)

### Features

- **engine**: Use ctx.stats.ones_are_wild in Columbo
  ([#133](https://github.com/after2400/liars-dice/pull/133),
  [`e023de1`](https://github.com/after2400/liars-dice/commit/e023de1400c2a41dbe1d4ed01b324ef59ef55b38))


## v2.2.0 (2026-06-30)

### Features

- **engine**: Add ones_are_wild to GameStats
  ([#134](https://github.com/after2400/liars-dice/pull/134),
  [`35802c7`](https://github.com/after2400/liars-dice/commit/35802c7fecbadfd004eca3fa1213921f46048b6b))


## v2.1.1 (2026-06-30)

### Bug Fixes

- **scripts**: Sort tier standings by current-run results; pin relegated players to top
  ([#130](https://github.com/after2400/liars-dice/pull/130),
  [`8387989`](https://github.com/after2400/liars-dice/commit/8387989f778d6e20128750123bcd114b7edaac7a))


## v2.1.0 (2026-06-30)

### Features

- **engine**: Simulation replay — deterministic re-runs with diff reports
  ([#128](https://github.com/after2400/liars-dice/pull/128),
  [`f6fe703`](https://github.com/after2400/liars-dice/commit/f6fe70373ce23ca524982d8490f26d8e18f1f5ca))


## v2.0.0 (2026-06-29)

### Features

- **engine**: V2.0.0 — SeriesResult API and Textual TUI
  ([#127](https://github.com/after2400/liars-dice/pull/127),
  [`055ae4b`](https://github.com/after2400/liars-dice/commit/055ae4b82263055a943ec26e6e65c814bbc9fcef))


## v1.12.2 (2026-06-25)

### Bug Fixes

- **engine**: Enter new players at lowest existing tier regardless of occupancy
  ([#117](https://github.com/after2400/liars-dice/pull/117),
  [`690edec`](https://github.com/after2400/liars-dice/commit/690edec04ae50c9306c3012de739724739efe57e))


## v1.12.1 (2026-06-25)

### Bug Fixes

- **engine**: Use display name in series results
  ([#115](https://github.com/after2400/liars-dice/pull/115),
  [`844b473`](https://github.com/after2400/liars-dice/commit/844b47312c61fee4ec48470d03b8b1fbdfddd004))


## v1.12.0 (2026-06-25)

### Features

- **engine**: Add dice_counts to GameStats
  ([#111](https://github.com/after2400/liars-dice/pull/111),
  [`1cd1781`](https://github.com/after2400/liars-dice/commit/1cd178162e7a2457bd222cab15b1ca806be79949))


## v1.11.0 (2026-06-20)

### Features

- **scripts**: Scan v1 players in weekly season summary
  ([#107](https://github.com/after2400/liars-dice/pull/107),
  [`d252f5f`](https://github.com/after2400/liars-dice/commit/d252f5fb1a5a7bafe53532278bc2a2631f4520f0))


## v1.10.0 (2026-06-20)

### Features

- **game**: GameContext v2 — immutable context object for algo() (#82)
  ([#83](https://github.com/after2400/liars-dice/pull/83),
  [`9169321`](https://github.com/after2400/liars-dice/commit/916932111231943da8ecb9e1f41c98018ede0c36))


## v1.9.0 (2026-06-19)

### Continuous Integration

- **workflows**: Add workflow_dispatch to sync-wiki for manual triggers
  ([#91](https://github.com/after2400/liars-dice/pull/91),
  [`c36c450`](https://github.com/after2400/liars-dice/commit/c36c450c500a615ca4926c32b5632ef0bcfd8447))

- **workflows**: Auto-update player PR branches when main advances
  ([#93](https://github.com/after2400/liars-dice/pull/93),
  [`cd43d3c`](https://github.com/after2400/liars-dice/commit/cd43d3cda48b9f2fc8aefab5c74f467f9b53d852))

- **workflows**: Grant contents: write so GITHUB_TOKEN can push to wiki
  ([#90](https://github.com/after2400/liars-dice/pull/90),
  [`b52bd81`](https://github.com/after2400/liars-dice/commit/b52bd81a4ea36ccf9004e4391bfbc268ddea8081))

### Documentation

- Add local simulation workflow to Player Guide wiki
  ([#88](https://github.com/after2400/liars-dice/pull/88),
  [`5e758f1`](https://github.com/after2400/liars-dice/commit/5e758f1796c5464dc04da04f7ce44aa8e187c15c))

### Features

- **game**: Add step counter, elapsed time, and generated-at timestamp to quarter sim
  ([#94](https://github.com/after2400/liars-dice/pull/94),
  [`46c24c7`](https://github.com/after2400/liars-dice/commit/46c24c7ded452206ccef16d478c71b4e60f86220))


## v1.8.0 (2026-06-19)

### Documentation

- Add just register-player recipe and document local registration
  ([#84](https://github.com/after2400/liars-dice/pull/84),
  [`cbdb237`](https://github.com/after2400/liars-dice/commit/cbdb237ad6c41d037453652c441dd3e628ec58c7))

### Features

- **scripts**: Add just simulate-quarter recipe and optional path to just clean
  ([#87](https://github.com/after2400/liars-dice/pull/87),
  [`743c689`](https://github.com/after2400/liars-dice/commit/743c6895689f5d1f7e1dfb0f81263ae4bc175340))


## v1.7.0 (2026-06-19)

### Continuous Integration

- Sync docs/wiki/ to GitHub wiki on merge (#79)
  ([#80](https://github.com/after2400/liars-dice/pull/80),
  [`1f07f57`](https://github.com/after2400/liars-dice/commit/1f07f57bc1695e619ab6fcbdd2316fb1c66298ae))

### Features

- **game**: Add round_players opt-in kwarg to algo() (#75)
  ([#78](https://github.com/after2400/liars-dice/pull/78),
  [`6bb7d1d`](https://github.com/after2400/liars-dice/commit/6bb7d1de71b2638009ea9642c9fc7ee49bdd66be))


## v1.6.2 (2026-06-18)

### Bug Fixes

- **game**: Grow PRM/CH to 8 before L1 resumes growth
  ([#76](https://github.com/after2400/liars-dice/pull/76),
  [`34f1122`](https://github.com/after2400/liars-dice/commit/34f112247686ae5c220d780bfaddaabf8f16a42e))


## v1.6.1 (2026-06-18)

### Bug Fixes

- **config**: Update simulate-tournament to use game.season.utils
  ([#72](https://github.com/after2400/liars-dice/pull/72),
  [`d218a84`](https://github.com/after2400/liars-dice/commit/d218a8498294f7748dc3bdd9d35ac40b19a96d3a))


## v1.6.0 (2026-06-18)

### Features

- **game**: Split L1 into pools when >8 players for season runs
  ([#70](https://github.com/after2400/liars-dice/pull/70),
  [`9e3e982`](https://github.com/after2400/liars-dice/commit/9e3e982153f58831f3ee19c5481ce3067c71969b))


## v1.5.1 (2026-06-18)

### Bug Fixes

- **game**: Scale tier capacity with player count in settle_relegations
  ([#71](https://github.com/after2400/liars-dice/pull/71),
  [`05af5e6`](https://github.com/after2400/liars-dice/commit/05af5e6d4b3c670722e9439d6419e4fe2f9c58aa))


## v1.5.0 (2026-06-18)

### Features

- **workflows**: Trigger season run automatically after new player registers
  ([#69](https://github.com/after2400/liars-dice/pull/69),
  [`d3bfbce`](https://github.com/after2400/liars-dice/commit/d3bfbce0b7609cb0ee58d03214ca95ad477fdc61))


## v1.4.8 (2026-06-18)

### Bug Fixes

- **workflows**: Serialize concurrent workflow runs
  ([#67](https://github.com/after2400/liars-dice/pull/67),
  [`a25962c`](https://github.com/after2400/liars-dice/commit/a25962ce8f5b1cd5c62282ba50b0080d4984a58f))


## v1.4.7 (2026-06-18)

### Bug Fixes

- **scripts**: Add time to season summary heading
  ([#68](https://github.com/after2400/liars-dice/pull/68),
  [`8016cce`](https://github.com/after2400/liars-dice/commit/8016ccede7f1971abc494ec56d69f4695943cedc))

### Chores

- **leaderboard**: Attribute Alice, Bruno, Cleo, Diego to zachaustin01
  ([#65](https://github.com/after2400/liars-dice/pull/65),
  [`0eff6bf`](https://github.com/after2400/liars-dice/commit/0eff6bfed30c862ade5359f65c8630bb89629822))


## v1.4.6 (2026-06-18)

### Bug Fixes

- **game**: Phase 3 operational hardening ([#64](https://github.com/after2400/liars-dice/pull/64),
  [`1297d9c`](https://github.com/after2400/liars-dice/commit/1297d9c9c8d9a52d899816da99cb435cf2f48b87))


## v1.4.5 (2026-06-18)

### Bug Fixes

- **game**: Replace exec_module() with AST-based player validator
  ([#63](https://github.com/after2400/liars-dice/pull/63),
  [`062ee54`](https://github.com/after2400/liars-dice/commit/062ee54a4a346219965015311328d43719a9591c))


## v1.4.4 (2026-06-18)

### Documentation

- Migrate player docs to wiki, trim CONTRIBUTING.md
  ([#57](https://github.com/after2400/liars-dice/pull/57),
  [`c25d4b0`](https://github.com/after2400/liars-dice/commit/c25d4b00a313e3b96f9c396a1cba5f1da7123340))

### Performance Improvements

- **game**: Isolate algo() inputs from shared game state
  ([#62](https://github.com/after2400/liars-dice/pull/62),
  [`56d0850`](https://github.com/after2400/liars-dice/commit/56d085055c53171566f1da974f02f0c3efe094a8))


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
