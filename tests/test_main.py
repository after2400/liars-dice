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


def test_class_name_used_in_series_results(tmp_path):
    """Series results dict (JSON) keys are class names, not display names."""

    from game.components.utils import import_player_classes_from_dir

    now = "2026-01-01T00:00:00Z"

    # Register every player file so none appears as "unregistered" (which would pull
    # them into --tier PRM). Alice and Bruno go in PRM; everyone else in inactive.
    all_names = {
        type(p).__name__ for p in import_player_classes_from_dir(str(REPO_ROOT / "players"))
    }

    def _entry(tier, display_name="", stats=None):
        return {
            "display_name": display_name,
            "github_username": "",
            "tier": tier,
            "date_added": now,
            "tier_since": now,
            "times_inactive": 0,
            "tier_stats": stats or {},
        }

    # Alice/Bruno: class name == display name — still the class name in results
    lb = {
        "total_runs": 1,
        "players": {
            name: _entry("PRM", "Alice", {"PRM": {"wins": 40, "games": 100, "win_pct": 40.0}})
            if name == "Alice"
            else _entry("PRM", "Bruno", {"PRM": {"wins": 30, "games": 100, "win_pct": 30.0}})
            if name == "Bruno"
            else _entry("inactive")
            for name in all_names
        },
    }
    results = run_game(["5", "4", "--tier", "PRM"], lb, tmp_path)
    assert set(results.keys()) == {"Alice", "Bruno"}

    # Nuke: class name "Nuke", display name "Nuke LaLoosh" — results use the class name
    nuke_entry = _entry("PRM", "Nuke LaLoosh", {"PRM": {"wins": 40, "games": 100, "win_pct": 40.0}})
    lb2 = {
        "total_runs": 1,
        "players": {
            name: nuke_entry
            if name == "Nuke"
            else _entry("PRM", "Bruno", {"PRM": {"wins": 30, "games": 100, "win_pct": 30.0}})
            if name == "Bruno"
            else _entry("inactive")
            for name in all_names
        },
    }
    results2 = run_game(["5", "4", "--tier", "PRM"], lb2, tmp_path)
    assert "Nuke" in results2, "class key expected, not display name"
    assert "Nuke LaLoosh" not in results2


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


def test_v2_player_receives_game_context(tmp_path):
    """A player with def algo(self, ctx) receives a GameContext instance."""
    import textwrap

    from game.components.series import run_series
    from game.components.utils import import_player_classes_from_dir

    player_src = textwrap.dedent("""
        from game.components.bets import Bet

        class V2Player:
            name = "V2Player"
            received = []
            def algo(self, ctx):
                V2Player.received.append(type(ctx).__name__)
                if ctx.prior_bet is None:
                    return Bet(1, 2, self.name)
                return None
    """)

    player_dir = tmp_path / "players"
    player_dir.mkdir()
    (player_dir / "v2player.py").write_text(player_src)
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
    assert len(spy_cls.received) > 0, "V2Player.algo was never called"
    assert all(t == "GameContext" for t in spy_cls.received), (
        f"Expected GameContext on every call, got: {spy_cls.received}"
    )


def test_v2_ctx_has_all_fields(tmp_path):
    """GameContext passed to v2 player has all expected fields populated."""
    import textwrap

    from game.components.series import run_series
    from game.components.utils import import_player_classes_from_dir

    player_src = textwrap.dedent("""
        from game.components.bets import Bet

        class FieldProbe:
            name = "FieldProbe"
            snapshots = []
            def algo(self, ctx):
                FieldProbe.snapshots.append({
                    "hand_type": type(ctx.hand).__name__,
                    "total_dice": ctx.total_dice,
                    "stats_type": type(ctx.stats).__name__,
                    "round_players_type": type(ctx.round_players).__name__,
                    "tier": ctx.tier,
                })
                if ctx.prior_bet is None:
                    return Bet(1, 2, self.name)
                return None
    """)

    player_dir = tmp_path / "players"
    player_dir.mkdir()
    (player_dir / "fieldprobe.py").write_text(player_src)
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
    probe_cls = players[0].__class__
    assert len(probe_cls.snapshots) > 0
    for snap in probe_cls.snapshots:
        assert snap["hand_type"] == "list"
        assert snap["total_dice"] > 0
        assert snap["stats_type"] == "GameStats"
        assert snap["round_players_type"] == "list"
        assert snap["tier"] == "CH"


def test_v1_and_v2_players_coexist(tmp_path):
    """A v1 and v2 player in the same game both work correctly."""
    import textwrap

    from game.components.series import run_series
    from game.components.utils import import_player_classes_from_dir

    v1_src = textwrap.dedent("""
        from game.components.bets import Bet

        class V1Player:
            name = "V1Player"
            calls = 0
            def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):
                V1Player.calls += 1
                if prior_bet is None:
                    return Bet(1, 2, self.name)
                return None
    """)

    v2_src = textwrap.dedent("""
        from game.components.bets import Bet

        class V2Player2:
            name = "V2Player2"
            calls = 0
            def algo(self, ctx):
                V2Player2.calls += 1
                if ctx.prior_bet is None:
                    return Bet(1, 2, self.name)
                return None
    """)

    player_dir = tmp_path / "players"
    player_dir.mkdir()
    (player_dir / "v1player.py").write_text(v1_src)
    (player_dir / "v2player2.py").write_text(v2_src)
    (player_dir / "__init__.py").write_text("")
    players = import_player_classes_from_dir(str(player_dir))

    run_series(players, n_games=3)
    v1_cls = next(p.__class__ for p in players if type(p).__name__ == "V1Player")
    v2_cls = next(p.__class__ for p in players if type(p).__name__ == "V2Player2")
    assert v1_cls.calls > 0, "V1Player was never called"
    assert v2_cls.calls > 0, "V2Player2 was never called"


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


def test_bet_history_entries_are_read_only(tmp_path):
    """bet_history entries passed to players are MappingProxyType — writes raise TypeError."""
    import textwrap

    from game.components.series import run_series
    from game.components.utils import import_player_classes_from_dir

    player_src = textwrap.dedent("""
        from game.components.bets import Bet

        class MutationProbe:
            name = "MutationProbe"
            saw_readonly = []
            def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):
                if bet_history:
                    try:
                        bet_history[-1]["player"] = "hacked"
                        MutationProbe.saw_readonly.append(False)
                    except TypeError:
                        MutationProbe.saw_readonly.append(True)
                if prior_bet is None:
                    from game.components.bets import Bet
                    return Bet(1, 2, self.name)
                return None
    """)

    player_dir = tmp_path / "players"
    player_dir.mkdir()
    (player_dir / "mutationprobe.py").write_text(player_src)
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
    probe_cls = players[0].__class__
    assert len(probe_cls.saw_readonly) > 0, "MutationProbe never saw a bet_history entry"
    assert all(probe_cls.saw_readonly), "bet_history entries were writable — expected TypeError"


def test_outcomes_hands_values_are_tuples(tmp_path):
    """outcomes[n]['hands'] values are tuples, not lists."""
    import textwrap

    from game.components.series import run_series
    from game.components.utils import import_player_classes_from_dir

    player_src = textwrap.dedent("""
        from game.components.bets import Bet

        class HandsProbe:
            name = "HandsProbe"
            hand_types = []
            def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):
                for outcome in outcomes:
                    for dice in outcome["hands"].values():
                        HandsProbe.hand_types.append(type(dice).__name__)
                if prior_bet is None:
                    return Bet(1, 2, self.name)
                return None
    """)

    player_dir = tmp_path / "players"
    player_dir.mkdir()
    (player_dir / "handsprobe.py").write_text(player_src)
    (player_dir / "__init__.py").write_text("")
    players = import_player_classes_from_dir(str(player_dir))

    class AlwaysBid:
        name = "AlwaysBid"

        def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):
            from game.components.bets import Bet

            if prior_bet is None:
                return Bet(1, 2, self.name)
            return Bet(prior_bet.quantity + 1, prior_bet.face, self.name)

    run_series(players + [AlwaysBid()], n_games=2)
    probe_cls = players[0].__class__
    assert len(probe_cls.hand_types) > 0, "HandsProbe never saw an outcome"
    assert all(t == "tuple" for t in probe_cls.hand_types), (
        f"Expected all tuple, got: {set(probe_cls.hand_types)}"
    )


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


def _make_outcome(bidder, challenger, bet_held, loser, hands, face=2):
    """Helper: build a minimal outcome dict for stats testing."""
    from game.components.bets import Bet

    return {
        "game": 1,
        "round": 1,
        "hands": {k: tuple(v) for k, v in hands.items()},
        "final_bet": Bet(1, face, bidder),
        "bidder": bidder,
        "challenger": challenger,
        "bet_held": bet_held,
        "loser": loser,
    }


def test_die_losses_from_bluff_tracked():
    """die_losses_from_bluff[loser][challenger] increments when bid fails."""
    from game.components.stats import GameStats

    s = GameStats()
    s.start_game(["Alice", "Bruno"])
    outcome = _make_outcome(
        bidder="Alice",
        challenger="Bruno",
        bet_held=False,
        loser="Alice",
        hands={"Alice": (1,), "Bruno": (2,)},
    )
    s.update_outcome(outcome)
    assert s.die_losses_from_bluff.get("Alice", {}).get("Bruno", 0) == 1
    assert s.die_losses_from_challenge.get("Bruno", {}).get("Alice", 0) == 0


def test_die_losses_from_challenge_tracked():
    """die_losses_from_challenge[loser][bidder] increments when call fails."""
    from game.components.stats import GameStats

    s = GameStats()
    s.start_game(["Alice", "Bruno"])
    outcome = _make_outcome(
        bidder="Alice",
        challenger="Bruno",
        bet_held=True,
        loser="Bruno",
        hands={"Alice": (2,), "Bruno": (1,)},
    )
    s.update_outcome(outcome)
    assert s.die_losses_from_challenge.get("Bruno", {}).get("Alice", 0) == 1
    assert s.die_losses_from_bluff.get("Alice", {}).get("Bruno", 0) == 0


def test_challenge_accuracy_by_face_tracked():
    """challenge_success_by_face and challenge_count_by_face increment on calls."""
    from game.components.stats import GameStats

    s = GameStats()
    s.start_game(["Alice", "Bruno"])
    success = _make_outcome(
        "Alice",
        "Bruno",
        bet_held=False,
        loser="Alice",
        hands={"Alice": (1,), "Bruno": (2,)},
        face=3,
    )
    fail = _make_outcome(
        "Alice", "Bruno", bet_held=True, loser="Bruno", hands={"Alice": (3,), "Bruno": (2,)}, face=3
    )
    s.update_outcome(success)
    s.update_outcome(fail)
    assert s.challenge_count_by_face.get("Bruno", {}).get(3, 0) == 2
    assert s.challenge_success_by_face.get("Bruno", {}).get(3, 0) == 1


def test_rounds_played_increments_per_hand_participant():
    """rounds_played increments for every player present in hands each round."""
    from game.components.stats import GameStats

    s = GameStats()
    s.start_game(["Alice", "Bruno", "Cleo"])
    outcome = _make_outcome(
        "Alice",
        "Bruno",
        bet_held=False,
        loser="Alice",
        hands={"Alice": (1,), "Bruno": (2,), "Cleo": (3,)},
    )
    s.update_outcome(outcome)
    assert s.rounds_played.get("Alice", 0) == 1
    assert s.rounds_played.get("Bruno", 0) == 1
    assert s.rounds_played.get("Cleo", 0) == 1


def test_games_played_increments_on_start_game():
    """games_played increments for each player when start_game is called."""
    from game.components.stats import GameStats

    s = GameStats()
    s.start_game(["Alice", "Bruno"])
    s.start_game(["Alice", "Bruno"])
    assert s.games_played.get("Alice", 0) == 2
    assert s.games_played.get("Bruno", 0) == 2


def test_record_penalty_increments():
    """record_penalty increments penalty_count for the named player."""
    from game.components.stats import GameStats

    s = GameStats()
    s.start_game(["Alice", "Bruno"])
    s.record_penalty("Alice")
    s.record_penalty("Alice")
    s.record_penalty("Bruno")
    assert s.penalty_count.get("Alice", 0) == 2
    assert s.penalty_count.get("Bruno", 0) == 1


def test_run_series_returns_series_result():
    """run_series returns a SeriesResult with wins and stats fields."""
    from game.components.series import SeriesResult, run_series

    class AlwaysBid:
        name = "A"

        def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):
            from game.components.bets import Bet

            return (
                Bet(1, 2, self.name)
                if prior_bet is None
                else Bet(prior_bet.quantity + 1, prior_bet.face, self.name)
            )

    class AlwaysCall:
        name = "B"

        def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):
            return None

    result = run_series([AlwaysBid(), AlwaysCall()], n_games=3)
    assert isinstance(result, SeriesResult)
    assert isinstance(result.wins, dict)
    assert sum(result.wins.values()) == 3
    assert result.stats is not None
    assert result.outcomes is None  # capture_outcomes defaults to False


def test_run_series_capture_outcomes():
    """run_series with capture_outcomes=True populates SeriesResult.outcomes."""
    from game.components.series import run_series

    class AlwaysBid:
        name = "A"

        def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):
            from game.components.bets import Bet

            return (
                Bet(1, 2, self.name)
                if prior_bet is None
                else Bet(prior_bet.quantity + 1, prior_bet.face, self.name)
            )

    class AlwaysCall:
        name = "B"

        def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):
            return None

    result = run_series([AlwaysBid(), AlwaysCall()], n_games=2, capture_outcomes=True)
    assert result.outcomes is not None
    assert len(result.outcomes) > 0


def test_on_game_complete_fires_each_game():
    """on_game_complete is called once per game with current wins and stats."""
    from game.components.series import run_series
    from game.components.stats import GameStats

    calls = []

    def callback(game_num, wins, stats):
        calls.append((game_num, dict(wins), isinstance(stats, GameStats)))

    class AlwaysBid:
        name = "A"

        def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):
            from game.components.bets import Bet

            return (
                Bet(1, 2, self.name)
                if prior_bet is None
                else Bet(prior_bet.quantity + 1, prior_bet.face, self.name)
            )

    class AlwaysCall:
        name = "B"

        def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):
            return None

    run_series([AlwaysBid(), AlwaysCall()], n_games=5, on_game_complete=callback)
    assert len(calls) == 5
    assert calls[0][0] == 1
    assert calls[4][0] == 5
    assert all(c[2] for c in calls)  # each call received a GameStats


def test_penalty_count_on_exception(tmp_path):
    """A player that raises an exception is penalised — penalty_count increments."""
    import textwrap

    from game.components.series import run_series
    from game.components.utils import import_player_classes_from_dir

    player_src = textwrap.dedent("""
        from game.components.bets import Bet

        class Crasher:
            name = "Crasher"
            def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):
                raise RuntimeError("boom")
    """)
    player_dir = tmp_path / "players"
    player_dir.mkdir()
    (player_dir / "crasher.py").write_text(player_src)
    (player_dir / "__init__.py").write_text("")

    class AlwaysBid:
        name = "AlwaysBid"

        def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):
            from game.components.bets import Bet

            return (
                Bet(1, 2, self.name)
                if prior_bet is None
                else Bet(prior_bet.quantity + 1, prior_bet.face, self.name)
            )

    players = import_player_classes_from_dir(str(player_dir))
    result = run_series(players + [AlwaysBid()], n_games=3)
    # Crasher crashes every round it plays (not just once per game), so count >= 3*1
    assert result.stats.penalty_count.get("Crasher", 0) >= 3


def test_tui_adapter_no_crash_without_app():
    """TuiAdapter methods are no-ops when the app is not running (no terminal needed)."""
    from game.components.stats import GameStats
    from game.tui import TuiAdapter

    wins = {"Oracle": 0, "EvilStewie": 0}
    stats = GameStats()
    stats.start_game(["Oracle", "EvilStewie"])

    adapter = TuiAdapter(n_games=10)
    # _app is None before .run() is called — all methods should be no-ops
    adapter.start_series("Test Series")
    wins["Oracle"] += 1
    adapter.update(1, wins, stats)
    adapter.on_series_complete("Test Series", None)


def test_simulation_season_run_season(tmp_path):
    """run_season runs tier games in-process and updates the leaderboard."""
    import textwrap

    import yaml

    from game.simulation.season import run_season

    # Build a minimal leaderboard with 2 L1 players
    lb = {
        "players": {
            "AliceBot": {"tier": "L1", "tier_stats": {}, "tier_since": "2026-01-01T00:00:00Z"},
            "BrunoBot": {"tier": "L1", "tier_stats": {}, "tier_since": "2026-01-01T00:00:00Z"},
        }
    }
    lb_path = str(tmp_path / "leaderboard.yaml")
    with open(lb_path, "w") as f:
        yaml.dump(lb, f)

    # Write stub player files
    players_dir = tmp_path / "players"
    players_dir.mkdir()
    for name in ("AliceBot", "BrunoBot"):
        (players_dir / f"{name.lower()}.py").write_text(
            textwrap.dedent(f"""
            from game.components.bets import Bet
            class {name}:
                name = "{name}"
                def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):
                    if prior_bet is None:
                        return Bet(1, 2, self.name)
                    return None
        """)
        )
    (players_dir / "__init__.py").write_text("")

    results = run_season(n_games=5, top_n=4, lb_path=lb_path, players_dir=str(players_dir))
    assert "L1" in results
    assert sum(results["L1"].values()) == 5


def test_simulation_tournament_run_tournament(tmp_path):
    """run_tournament runs pool games and assigns placements."""
    import textwrap

    import yaml

    from game.simulation.tournament import run_tournament

    lb = {
        "players": {
            "AliceBot": {"tier": "L1", "tier_stats": {}, "tier_since": "2026-01-01T00:00:00Z"},
            "BrunoBot": {"tier": "L1", "tier_stats": {}, "tier_since": "2026-01-01T00:00:00Z"},
            "CleoBot": {"tier": "CH", "tier_stats": {}, "tier_since": "2026-01-01T00:00:00Z"},
            "DaveBot": {"tier": "PRM", "tier_stats": {}, "tier_since": "2026-01-01T00:00:00Z"},
        },
        "tournament_state": {},
    }
    lb_path = str(tmp_path / "leaderboard.yaml")
    with open(lb_path, "w") as f:
        yaml.dump(lb, f)

    players_dir = tmp_path / "players"
    players_dir.mkdir()
    for name in ("AliceBot", "BrunoBot", "CleoBot", "DaveBot"):
        (players_dir / f"{name.lower()}.py").write_text(
            textwrap.dedent(f"""
            from game.components.bets import Bet
            class {name}:
                name = "{name}"
                def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):
                    if prior_bet is None:
                        return Bet(1, 2, self.name)
                    return None
        """)
        )
    (players_dir / "__init__.py").write_text("")

    pool_results = run_tournament(n_games=5, lb_path=lb_path, players_dir=str(players_dir))
    assert len(pool_results) >= 1
    # After assignment, all players should have a tier
    import yaml

    with open(lb_path) as f:
        data = yaml.safe_load(f)
    tiers = {p["tier"] for p in data["players"].values()}
    assert tiers <= {"PRM", "CH", "L1", "DED", "inactive"}


def test_perf_tracker_records_calls_for_each_player():
    """game_orchestrator(perf=tracker) records one call per player per turn taken."""
    from game.components.perf import PerfTracker

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

    tracker = PerfTracker()
    game_orchestrator([Bidder(), Caller()], bet_history=[], perf=tracker)

    assert tracker.call_count("Bidder") >= 1
    assert tracker.call_count("Caller") >= 1


def test_perf_tracker_records_call_even_when_player_raises():
    """A player that raises still gets its call timed (finally runs before re-raise)."""
    from game.components.perf import PerfTracker

    class Crasher:
        name = "Crasher"

        def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):
            raise RuntimeError("boom")

    class AlwaysBid:
        name = "AlwaysBid"

        def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):
            if prior_bet is None:
                return Bet(1, 2, self.name)
            return Bet(prior_bet.quantity + 1, prior_bet.face, self.name)

    tracker = PerfTracker()
    game_orchestrator([Crasher(), AlwaysBid()], bet_history=[], perf=tracker)

    assert tracker.call_count("Crasher") >= 1


def test_game_orchestrator_runs_without_perf_tracker():
    """perf=None (the default) must not change existing behaviour."""

    class Caller:
        name = "Caller"

        def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):
            return None

    class Bidder:
        name = "Bidder"

        def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):
            if prior_bet is None:
                return Bet(1, 2, self.name)
            return Bet(prior_bet.quantity + 1, prior_bet.face, self.name)

    winner = game_orchestrator([Bidder(), Caller()], bet_history=[])
    assert winner is not None


def test_run_series_perf_tracker_accumulates_across_games():
    """run_series(perf=tracker) records calls across all games, not just one."""
    from game.components.perf import PerfTracker
    from game.components.series import run_series

    class Caller:
        name = "Caller"

        def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):
            return None

    class Bidder:
        name = "Bidder"

        def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):
            if prior_bet is None:
                return Bet(1, 2, self.name)
            return Bet(prior_bet.quantity + 1, prior_bet.face, self.name)

    tracker = PerfTracker()
    result = run_series([Bidder(), Caller()], n_games=3, perf=tracker)

    assert result.perf is tracker
    assert tracker.call_count("Bidder") >= 3
    assert tracker.call_count("Caller") >= 3


def test_run_series_perf_defaults_to_none():
    from game.components.series import run_series

    class Caller:
        name = "Caller"

        def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):
            return None

    class Bidder:
        name = "Bidder"

        def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):
            if prior_bet is None:
                return Bet(1, 2, self.name)
            return Bet(prior_bet.quantity + 1, prior_bet.face, self.name)

    result = run_series([Bidder(), Caller()], n_games=1)
    assert result.perf is None
