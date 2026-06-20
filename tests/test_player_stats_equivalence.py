"""Verify that stats-path and scan-path produce identical results for Eva and Sloane.

These tests exist because GameStats must provide *raw* (unsmoothed) bluff rates
to exactly match the scan-based helpers those players used before migration.
"""

from unittest.mock import MagicMock

import pytest


def _make_outcome(bidder: str, face: int, held: bool) -> dict:
    fb = MagicMock()
    fb.face = face
    fb.quantity = 5
    return {
        "game": 1,
        "round": 1,
        "hands": {},
        "final_bet": fb,
        "bidder": bidder,
        "challenger": "Other",
        "bet_held": held,
        "loser": "Other" if held else bidder,
    }


def _build_stats(outcomes):
    from game.components.stats import GameStats

    stats = GameStats()
    for o in outcomes:
        stats.update_outcome(o)
    return stats


# ---------------------------------------------------------------------------
# Eva
# ---------------------------------------------------------------------------


def test_eva_raw_bluff_rate_matches_reliability_scan():
    """stats.raw_bluff_rate must equal 1 - eva._reliability for the same data."""
    from players.eva import Eva

    eva = Eva()
    outcomes = [
        _make_outcome("Alice", 3, False),
        _make_outcome("Alice", 3, False),
        _make_outcome("Alice", 3, False),
        _make_outcome("Alice", 3, True),
    ]
    stats = _build_stats(outcomes)
    # scan: 1 - reliability = 1 - 1/4 = 0.75
    scan_bluff_rate = 1 - eva._reliability("Alice", outcomes)
    stats_bluff_rate = stats.raw_bluff_rate.get("Alice", 0.5)
    assert scan_bluff_rate == pytest.approx(stats_bluff_rate)


# ---------------------------------------------------------------------------
# Sloane
# ---------------------------------------------------------------------------


def test_sloane_raw_bluff_rate_by_face_matches_delta_bias_scan():
    """stats.raw_bluff_rate_by_face must reproduce Sloane's _calculate_delta_bias."""
    from players.sloane import Sloane

    sloane = Sloane()
    outcomes = [
        _make_outcome("Alice", 3, False),
        _make_outcome("Alice", 3, False),
        _make_outcome("Alice", 3, True),
    ]
    stats = _build_stats(outcomes)
    # scan: reliability = 1/3, delta_bias = (0.5 - 1/3) * 0.2 ≈ 0.0333
    scan_delta = sloane._calculate_delta_bias("Alice", 3, outcomes)
    # stats: raw face bluff_rate = 2/3, delta = (2/3 - 0.5) * 0.2 ≈ 0.0333
    raw_face_rate = stats.raw_bluff_rate_by_face.get("Alice", {}).get(3, 0.5)
    stats_delta = (raw_face_rate - 0.5) * 0.2
    assert scan_delta == pytest.approx(stats_delta)
