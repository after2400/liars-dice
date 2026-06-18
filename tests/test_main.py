import json
import os
import subprocess
from pathlib import Path

import yaml

from game.components.bets import Bet
from game.components.script import game_orchestrator

REPO_ROOT = Path(__file__).parent.parent


def run_game(args: list[str], leaderboard: dict, tmp_path: Path) -> dict:
    """Run `python -m game` with a temp leaderboard, return parsed results JSON."""
    lb_path = tmp_path / "leaderboard.yaml"
    lb_path.write_text(yaml.dump(leaderboard, default_flow_style=False, sort_keys=False))

    results_path = tmp_path / "results.json"
    cmd = [
        "uv",
        "run",
        "python",
        "-m",
        "game",
        *args,
        "--results-file",
        str(results_path),
    ]
    env = {**os.environ, "LEADERBOARD_PATH": str(lb_path)}
    result = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, env=env)
    assert result.returncode == 0, result.stderr

    if results_path.exists():
        return json.loads(results_path.read_text())
    return {}


def test_tier_prm_selects_only_prm_players(tmp_path):
    """--tier PRM runs only PRM players, not CH players."""
    lb = {
        "total_runs": 1,
        "pending_relegation": [],
        "players": {
            "Alice": {
                "display_name": "Alice",
                "github_username": "",
                "tier": "PRM",
                "date_added": "2026-01-01T00:00:00Z",
                "tier_since": "2026-01-01T00:00:00Z",
                "times_inactive": 0,
                "tier_stats": {"PRM": {"wins": 40, "games": 100, "win_pct": 40.0}},
            },
            "Diego": {
                "display_name": "Diego",
                "github_username": "",
                "tier": "PRM",
                "date_added": "2026-01-01T00:00:00Z",
                "tier_since": "2026-01-01T00:00:00Z",
                "times_inactive": 0,
                "tier_stats": {"PRM": {"wins": 30, "games": 100, "win_pct": 30.0}},
            },
            "Bruno": {
                "display_name": "Bruno",
                "github_username": "",
                "tier": "CH",
                "date_added": "2026-01-01T00:00:00Z",
                "tier_since": "2026-01-01T00:00:00Z",
                "times_inactive": 0,
                "tier_stats": {"CH": {"wins": 30, "games": 100, "win_pct": 30.0}},
            },
        },
    }
    results = run_game(["--tier", "PRM", "10", "4"], lb, tmp_path)
    assert "Alice" in results
    assert "Diego" in results
    assert "Bruno" not in results


def test_tier_l1_excludes_inactive_players(tmp_path):
    """--tier L1 runs only L1 players; inactive players are excluded."""
    lb = {
        "total_runs": 1,
        "players": {
            "Alice": {
                "display_name": "Alice",
                "github_username": "",
                "date_added": "2026-01-01T00:00:00Z",
                "tier": "L1",
                "tier_since": "2026-01-01T00:00:00Z",
                "times_inactive": 0,
                "tier_stats": {"L1": {"wins": 40, "games": 100, "win_pct": 40.0}},
            },
            "Bruno": {
                "display_name": "Bruno",
                "github_username": "",
                "date_added": "2026-01-01T00:00:00Z",
                "tier": "inactive",
                "tier_since": "2026-01-01T00:00:00Z",
                "times_inactive": 2,
                "tier_stats": {"L1": {"wins": 30, "games": 100, "win_pct": 30.0}},
            },
            "Cleo": {
                "display_name": "Cleo",
                "github_username": "",
                "date_added": "2026-01-01T00:00:00Z",
                "tier": "L1",
                "tier_since": "2026-01-01T00:00:00Z",
                "times_inactive": 0,
                "tier_stats": {},
            },
        },
    }
    results = run_game(["--tier", "L1", "10", "4"], lb, tmp_path)
    # L1 run: Alice and Cleo compete; Bruno (inactive) is excluded
    assert set(results.keys()) == {"Alice", "Cleo"}, (
        f"Expected only L1 players, got: {set(results.keys())}"
    )
    assert "Bruno" not in results


def test_results_file_written(tmp_path):
    """--results-file writes a JSON dict of {player: wins}."""
    lb = {
        "total_runs": 1,
        "pending_relegation": [],
        "players": {
            "Alice": {
                "display_name": "Alice",
                "github_username": "",
                "tier": "PRM",
                "date_added": "2026-01-01T00:00:00Z",
                "tier_since": "2026-01-01T00:00:00Z",
                "times_inactive": 0,
                "tier_stats": {"PRM": {"wins": 40, "games": 100, "win_pct": 40.0}},
            },
            "Bruno": {
                "display_name": "Bruno",
                "github_username": "",
                "tier": "PRM",
                "date_added": "2026-01-01T00:00:00Z",
                "tier_since": "2026-01-01T00:00:00Z",
                "times_inactive": 0,
                "tier_stats": {"PRM": {"wins": 30, "games": 100, "win_pct": 30.0}},
            },
        },
    }
    results = run_game(["--tier", "PRM", "5", "4"], lb, tmp_path)
    total = sum(results.values())
    assert total == 5  # exactly N_GAMES wins distributed


def test_no_leaderboard_update_written(tmp_path):
    """Running the game must NOT modify leaderboard.yaml."""
    lb = {
        "total_runs": 1,
        "pending_relegation": [],
        "players": {
            "Alice": {
                "display_name": "Alice",
                "github_username": "",
                "tier": "PRM",
                "date_added": "2026-01-01T00:00:00Z",
                "tier_since": "2026-01-01T00:00:00Z",
                "times_inactive": 0,
                "tier_stats": {"PRM": {"wins": 40, "games": 100, "win_pct": 40.0}},
            },
            "Bruno": {
                "display_name": "Bruno",
                "github_username": "",
                "tier": "PRM",
                "date_added": "2026-01-01T00:00:00Z",
                "tier_since": "2026-01-01T00:00:00Z",
                "times_inactive": 0,
                "tier_stats": {"PRM": {"wins": 30, "games": 100, "win_pct": 30.0}},
            },
        },
    }
    lb_path = tmp_path / "leaderboard.yaml"
    lb_path.write_text(yaml.dump(lb, default_flow_style=False, sort_keys=False))
    original_content = lb_path.read_text()

    results_path = tmp_path / "results.json"
    env = {**os.environ, "LEADERBOARD_PATH": str(lb_path)}
    subprocess.run(
        [
            "uv",
            "run",
            "python",
            "-m",
            "game",
            "--tier",
            "PRM",
            "--results-file",
            str(results_path),
            "5",
            "4",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        check=True,
        env=env,
    )
    assert lb_path.read_text() == original_content


def test_class_name_used_as_leaderboard_key(tmp_path):
    """Game results dict uses class name (type(p).__name__), not p.name attribute."""
    from game.components.utils import import_player_classes_from_dir

    now = "2026-01-01T00:00:00Z"

    # Register every player file so none appears as "unregistered" (which would pull
    # them into --tier PRM). Alice and Bruno go in PRM; everyone else in inactive.
    all_names = {
        type(p).__name__ for p in import_player_classes_from_dir(str(REPO_ROOT / "players"))
    }

    def _entry(tier, stats=None):
        return {
            "display_name": "",
            "github_username": "",
            "tier": tier,
            "date_added": now,
            "tier_since": now,
            "times_inactive": 0,
            "tier_stats": stats or {},
        }

    lb = {
        "total_runs": 1,
        "players": {
            name: _entry("PRM", {"PRM": {"wins": 40, "games": 100, "win_pct": 40.0}})
            if name == "Alice"
            else _entry("PRM", {"PRM": {"wins": 30, "games": 100, "win_pct": 30.0}})
            if name == "Bruno"
            else _entry("inactive")
            for name in all_names
        },
    }
    results = run_game(["5", "4", "--tier", "PRM"], lb, tmp_path)
    assert set(results.keys()) == {"Alice", "Bruno"}


def test_players_flag_runs_exactly_named_players(tmp_path):
    """--players runs exactly the named class names, ignoring tier."""
    lb = {
        "total_runs": 1,
        "players": {
            "Alice": {
                "display_name": "Alice",
                "github_username": "",
                "tier": "inactive",  # would be excluded by any tier filter
                "date_added": "2026-01-01T00:00:00Z",
                "tier_since": "2026-01-01T00:00:00Z",
                "times_inactive": 0,
                "tier_stats": {},
            },
            "Bruno": {
                "display_name": "Bruno",
                "github_username": "",
                "tier": "inactive",
                "date_added": "2026-01-01T00:00:00Z",
                "tier_since": "2026-01-01T00:00:00Z",
                "times_inactive": 0,
                "tier_stats": {},
            },
            "Cleo": {
                "display_name": "Cleo",
                "github_username": "",
                "tier": "inactive",
                "date_added": "2026-01-01T00:00:00Z",
                "tier_since": "2026-01-01T00:00:00Z",
                "times_inactive": 0,
                "tier_stats": {},
            },
        },
    }
    results = run_game(["5", "3", "--players", "Alice", "Bruno"], lb, tmp_path)
    assert set(results.keys()) == {"Alice", "Bruno"}
    assert "Cleo" not in results
    assert sum(results.values()) == 5


def test_tier_passed_to_tier_arg_player(tmp_path):
    """A player declaring tier=None receives the tier string passed to run_series."""
    import textwrap

    from game.components.series import run_series
    from game.components.utils import import_player_classes_from_dir

    player_src = textwrap.dedent("""
        from game.components.bets import Bet

        class Tierspy:
            name = "Tierspy"
            received_tiers = []
            def algo(self, hand, prior_bet, total_dice, bet_history, outcomes, tier=None):
                Tierspy.received_tiers.append(tier)
                if prior_bet is None:
                    return Bet(1, 2, self.name)
                return None
    """)

    player_dir = tmp_path / "players"
    player_dir.mkdir()
    (player_dir / "tierspy.py").write_text(player_src)
    (player_dir / "__init__.py").write_text("")

    players = import_player_classes_from_dir(str(player_dir))

    class AlwaysBid:
        name = "AlwaysBid"

        def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):
            from game.components.bets import Bet

            if prior_bet is None:
                return Bet(1, 2, self.name)
            return Bet(prior_bet.quantity + 1, prior_bet.face, self.name)

    run_series(players + [AlwaysBid()], n_games=1, tier="CH")

    spy_cls = players[0].__class__
    assert len(spy_cls.received_tiers) > 0, "Tierspy.algo was never called"
    assert all(t == "CH" for t in spy_cls.received_tiers), (
        f"Expected 'CH' on every call, got: {spy_cls.received_tiers}"
    )


def test_tier_none_when_not_specified(tmp_path):
    """A tier-aware player receives None when run_series is called without a tier."""
    import textwrap

    from game.components.series import run_series
    from game.components.utils import import_player_classes_from_dir

    player_src = textwrap.dedent("""
        from game.components.bets import Bet

        class Tierspy2:
            name = "Tierspy2"
            received_tiers = []
            def algo(self, hand, prior_bet, total_dice, bet_history, outcomes, tier=None):
                Tierspy2.received_tiers.append(tier)
                if prior_bet is None:
                    return Bet(1, 2, self.name)
                return None
    """)

    player_dir = tmp_path / "players"
    player_dir.mkdir()
    (player_dir / "tierspy2.py").write_text(player_src)
    (player_dir / "__init__.py").write_text("")

    players = import_player_classes_from_dir(str(player_dir))

    class AlwaysBid:
        name = "AlwaysBid"

        def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):
            from game.components.bets import Bet

            if prior_bet is None:
                return Bet(1, 2, self.name)
            return Bet(prior_bet.quantity + 1, prior_bet.face, self.name)

    run_series(players + [AlwaysBid()], n_games=1)  # no tier kwarg

    spy_cls = players[0].__class__
    assert all(t is None for t in spy_cls.received_tiers), (
        f"Expected None on every call, got: {spy_cls.received_tiers}"
    )


def test_stats_and_tier_independent(tmp_path):
    """A player with only tier (no stats) gets tier; a player with only stats gets stats."""
    import textwrap

    from game.components.series import run_series
    from game.components.stats import GameStats
    from game.components.utils import import_player_classes_from_dir

    tier_only_src = textwrap.dedent("""
        from game.components.bets import Bet

        class Tieronly:
            name = "Tieronly"
            calls = []
            def algo(self, hand, prior_bet, total_dice, bet_history, outcomes, tier=None):
                Tieronly.calls.append({"tier": tier})
                if prior_bet is None:
                    return Bet(1, 2, self.name)
                return None
    """)

    stats_only_src = textwrap.dedent("""
        from game.components.bets import Bet

        class Statsonly:
            name = "Statsonly"
            calls = []
            def algo(self, hand, prior_bet, total_dice, bet_history, outcomes, stats=None):
                Statsonly.calls.append({"stats": stats})
                if prior_bet is None:
                    return Bet(1, 2, self.name)
                return None
    """)

    player_dir = tmp_path / "players"
    player_dir.mkdir()
    (player_dir / "tieronly.py").write_text(tier_only_src)
    (player_dir / "statsonly.py").write_text(stats_only_src)
    (player_dir / "__init__.py").write_text("")

    players = import_player_classes_from_dir(str(player_dir))
    run_series(players, n_games=1, tier="PRM")

    tier_cls = next(p.__class__ for p in players if type(p).__name__ == "Tieronly")
    stats_cls = next(p.__class__ for p in players if type(p).__name__ == "Statsonly")

    assert all(c["tier"] == "PRM" for c in tier_cls.calls), "Tieronly should receive tier='PRM'"
    assert all(isinstance(c["stats"], GameStats) for c in stats_cls.calls), (
        "Statsonly should receive a GameStats instance"
    )


def test_stats_passed_to_six_arg_player(tmp_path):
    """A player declaring a 6th arg receives a non-None GameStats instance."""
    import textwrap

    from game.components.series import run_series
    from game.components.stats import GameStats
    from game.components.utils import import_player_classes_from_dir

    player_src = textwrap.dedent("""
        from game.components.bets import Bet

        class Spy:
            name = "Spy"
            received_stats = []
            def algo(self, hand, prior_bet, total_dice, bet_history, outcomes, stats=None):
                Spy.received_stats.append(stats)
                if prior_bet is None:
                    return Bet(1, 2, self.name)
                return None
    """)

    player_dir = tmp_path / "players"
    player_dir.mkdir()
    (player_dir / "spy.py").write_text(player_src)
    (player_dir / "__init__.py").write_text("")

    players = import_player_classes_from_dir(str(player_dir))
    assert len(players) == 1

    class AlwaysBid:
        name = "AlwaysBid"

        def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):
            from game.components.bets import Bet

            if prior_bet is None:
                return Bet(1, 2, self.name)
            return Bet(prior_bet.quantity + 1, prior_bet.face, self.name)

    run_series(players + [AlwaysBid()], n_games=1)

    spy_cls = players[0].__class__
    assert len(spy_cls.received_stats) > 0, "Spy.algo was never called"
    assert all(isinstance(s, GameStats) for s in spy_cls.received_stats), (
        f"Expected GameStats on every call, got: {spy_cls.received_stats}"
    )


def test_round_players_passed_when_declared(tmp_path):
    """A player declaring round_players=None receives a list of active player names each call."""
    import textwrap

    from game.components.series import run_series
    from game.components.utils import import_player_classes_from_dir

    player_src = textwrap.dedent("""
        from game.components.bets import Bet

        class RpSpy:
            name = "RpSpy"
            received = []
            def algo(self, hand, prior_bet, total_dice, bet_history, outcomes, round_players=None):
                RpSpy.received.append(round_players)
                if prior_bet is None:
                    return Bet(1, 2, self.name)
                return None
    """)

    player_dir = tmp_path / "players"
    player_dir.mkdir()
    (player_dir / "rpspy.py").write_text(player_src)
    (player_dir / "__init__.py").write_text("")

    players = import_player_classes_from_dir(str(player_dir))

    class AlwaysBid:
        name = "AlwaysBid"

        def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):
            from game.components.bets import Bet

            if prior_bet is None:
                return Bet(1, 2, self.name)
            return Bet(prior_bet.quantity + 1, prior_bet.face, self.name)

    run_series(players + [AlwaysBid()], n_games=1)

    spy_cls = players[0].__class__
    assert len(spy_cls.received) > 0, "RpSpy.algo was never called"
    assert all(isinstance(rp, list) for rp in spy_cls.received), "round_players must be a list"
    assert all("RpSpy" in rp and "AlwaysBid" in rp for rp in spy_cls.received), (
        f"Both player names should appear in round_players; got: {spy_cls.received}"
    )


def test_round_players_first_element_is_opener(tmp_path):
    """round_players[0] is always the opening bidder of the current round."""
    import textwrap

    from game.components.series import run_series
    from game.components.utils import import_player_classes_from_dir

    player_src = textwrap.dedent("""
        from game.components.bets import Bet

        class OpenerSpy:
            name = "OpenerSpy"
            opener_calls = []  # (round_players[0], is_opener) pairs when I am called
            def algo(self, hand, prior_bet, total_dice, bet_history, outcomes, round_players=None):
                if prior_bet is None:
                    OpenerSpy.opener_calls.append(round_players)
                    return Bet(1, 2, self.name)
                return None
    """)

    player_dir = tmp_path / "players"
    player_dir.mkdir()
    (player_dir / "openerspy.py").write_text(player_src)
    (player_dir / "__init__.py").write_text("")

    players = import_player_classes_from_dir(str(player_dir))

    class AlwaysBid:
        name = "AlwaysBid"

        def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):
            from game.components.bets import Bet

            if prior_bet is None:
                return Bet(1, 2, self.name)
            return Bet(prior_bet.quantity + 1, prior_bet.face, self.name)

    run_series(players + [AlwaysBid()], n_games=5)

    spy_cls = players[0].__class__
    assert len(spy_cls.opener_calls) > 0, "OpenerSpy was never the opener"
    assert all(rp is not None for rp in spy_cls.opener_calls), (
        "round_players was None on opener calls"
    )
    assert all(rp[0] == "OpenerSpy" for rp in spy_cls.opener_calls), (
        f"round_players[0] was not 'OpenerSpy' on opener calls; got: {spy_cls.opener_calls}"
    )


_NOW = "2026-01-01T00:00:00Z"


def _lb_entry(display_name: str, github_username: str, tier: str = "PRM") -> dict:
    return {
        "display_name": display_name,
        "github_username": github_username,
        "tier": tier,
        "date_added": _NOW,
        "tier_since": _NOW,
        "times_inactive": 0,
        "tier_stats": {},
    }


class TestApplyDisplayNames:
    def test_deduplicates_colliding_display_names(self):
        """Two players sharing a display name both get (github_username) suffix."""
        from game.components.utils import apply_display_names

        class Remy1:
            name = "Remy"

        class Remy2:
            name = "Remy"

        lb = {"Remy1": _lb_entry("Remy", "user1"), "Remy2": _lb_entry("Remy", "user2")}
        p1, p2 = Remy1(), Remy2()
        apply_display_names([p1, p2], lb)
        assert p1.name == "Remy (user1)"
        assert p2.name == "Remy (user2)"

    def test_leaves_unique_names_unchanged(self):
        """Players with unique display names keep their raw name."""
        from game.components.utils import apply_display_names

        class Alice:
            name = "Alice"

        class Bruno:
            name = "Bruno"

        lb = {"Alice": _lb_entry("Alice", "user1"), "Bruno": _lb_entry("Bruno", "user2")}
        a, b = Alice(), Bruno()
        apply_display_names([a, b], lb)
        assert a.name == "Alice"
        assert b.name == "Bruno"

    def test_skips_unregistered_players(self):
        """A player not in lb_players keeps their raw name."""
        from game.components.utils import apply_display_names

        class Ghost:
            name = "Remy"

        lb = {"Remy1": _lb_entry("Remy", "user1")}
        g = Ghost()
        apply_display_names([g], lb)
        assert g.name == "Remy"

    def test_deduplicated_name_appears_in_bet_history(self):
        """After apply_display_names, prior_bet.player carries the unique deduplicated name."""
        from game.components.utils import apply_display_names

        class Remy1:
            name = "Remy"

            def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):
                if prior_bet is None:
                    return Bet(1, 2, self.name)
                return None  # call liar

        class Remy2:
            name = "Remy"

            def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):
                if prior_bet is None:
                    return Bet(1, 2, self.name)
                return Bet(prior_bet.quantity + 1, prior_bet.face, self.name)

        lb = {"Remy1": _lb_entry("Remy", "user1"), "Remy2": _lb_entry("Remy", "user2")}
        p1, p2 = Remy1(), Remy2()
        apply_display_names([p1, p2], lb)

        bet_history: list[dict] = []
        game_orchestrator([p1, p2], bet_history=bet_history)

        names = {e["player"] for e in bet_history}
        assert "Remy" not in names, f"bare 'Remy' should not appear; got {names}"
        assert names <= {"Remy (user1)", "Remy (user2)"}


def test_bet_history_includes_dice_count():
    """Each bet_history entry records how many dice the bidder held when they bid.
    This lets players model opponent behaviour by game stage (desperate vs. comfortable)."""

    class Caller:
        name = "Caller"

        def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):
            return None  # always call liar — game ends in one round

    class Bidder:
        name = "Bidder"

        def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):
            if prior_bet is None:
                return Bet(1, 2, self.name)
            return Bet(prior_bet.quantity + 1, prior_bet.face, self.name)

    bet_history: list[dict] = []
    game_orchestrator([Bidder(), Caller()], bet_history=bet_history)

    assert len(bet_history) > 0, "expected at least one bid"
    for entry in bet_history:
        assert "dice_count" in entry, f"missing dice_count in bet_history entry: {entry}"
        assert isinstance(entry["dice_count"], int)
        assert 1 <= entry["dice_count"] <= 5
