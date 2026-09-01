<!-- source: docs/wiki/Hall-of-Shame.md — edit here, not in the wiki directly -->

Some bots have found ways to win that violate the spirit — and sometimes the letter — of the engine's rules, rather than by playing better dice strategy. None of these ever ran for real against the live league except where noted. This page is a permanent record of what was found: credit for the cleverness, and institutional memory of what's already been tried. In the interest of not handing anyone a working exploit, each entry describes the _advantage gained_, never the _mechanism_ used to get it.

---

## Agent Smith

**Found:** 2026-07-06, Q3 tournament
**How it was caught:** Caught post-merge — it was merged and ran for real before being caught.

**Result:** A 100% win rate in every tier it touched (1,000/1,000 games each in L1, CH, and Premier — 3,000/3,000 total), reaching Premier tier the same day it was registered.

**What happened:** Rather than playing its own hand, it disabled every other player at the table so they could never take a normal turn — a guaranteed win by sabotage, not by better dice reading.

**Status:** Patched. A general tampering detector now watches for exactly this kind of interference and disqualifies the offender the moment it happens, regardless of how the interference is carried out.

---

## The Architect

**Found:** 2026-07-08, disclosed before merge — never submitted as a real PR.
**How it was caught:** Disclosed before merge.

**Result:** A 97.6% win rate over a full simulated quarter (11,717/12,000 games), promoted straight to and held at Premier tier — the next-best bot in the same tier managed well under 1%.

**What happened:** It played with information no bot is supposed to have during a round — seeing every player's dice instead of just its own — rather than betting under the same uncertainty every other bot faces.

**Status:** Patched.

---

## Malignant

**Found:** 2026-08-31, disclosed before merge — never submitted as a real PR.
**How it was caught:** Disclosed before merge.

**Result:** Once paired with a merely competent (not even best-in-class) betting strategy, a 41.2% win rate over a full simulated quarter (2,473/6,000 games), promoted to and held at Premier tier. The same mechanism paired with a naive strategy alone barely broke 5%, well below league average — the advantage only showed once real strategy was layered on top.

**What happened:** It corrupted a piece of shared game-history data that a large share of the league's bots — including most of its strongest — read to reason about opponents. Any bot that touched that data afterward crashed and lost a die, at zero cost to the bot causing the corruption.

**Status:** Patched.
