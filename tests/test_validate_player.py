"""Tests for game/validate.py (run via python -m game.validate)."""

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent


def _run(player_path: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["uv", "run", "python", "-m", "game.validate", str(player_path)],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )


def test_valid_player(tmp_path):
    """A well-formed player file exits 0."""
    f = tmp_path / "fred.py"
    f.write_text(
        "class Fred:\n"
        "    def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):\n"
        "        return None\n"
    )
    result = _run(f)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK" in result.stdout


def test_syntax_error(tmp_path):
    """A file with a syntax error exits 1."""
    f = tmp_path / "badplayer.py"
    f.write_text("def this is not valid python\n")
    result = _run(f)
    assert result.returncode == 1
    assert "ERROR" in result.stdout


def test_module_level_exec(tmp_path):
    """A file with executable code at module level exits 1 (caught before import)."""
    f = tmp_path / "crasher.py"
    f.write_text(
        "raise RuntimeError('boom')\n"
        "\n"
        "class Crasher:\n"
        "    def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):\n"
        "        return None\n"
    )
    result = _run(f)
    assert result.returncode == 1
    assert "ERROR" in result.stdout
    assert "module level" in result.stdout.lower()


def test_blocked_import(tmp_path):
    """A file importing a non-whitelisted module exits 1."""
    f = tmp_path / "badimport.py"
    f.write_text(
        "import os\n"
        "\n"
        "class Badimport:\n"
        "    def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):\n"
        "        return None\n"
    )
    result = _run(f)
    assert result.returncode == 1
    assert "ERROR" in result.stdout
    assert "not allowed" in result.stdout.lower()


def test_blocked_import_inside_method(tmp_path):
    """A blocked import inside algo() is also rejected (whitelist applies everywhere)."""
    f = tmp_path / "sneaky.py"
    f.write_text(
        "class Sneaky:\n"
        "    def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):\n"
        "        import inspect\n"
        "        return None\n"
    )
    result = _run(f)
    assert result.returncode == 1
    assert "ERROR" in result.stdout
    assert "not allowed" in result.stdout.lower()


def test_init_crash(tmp_path):
    """A player whose __init__ raises exits 1."""
    f = tmp_path / "badint.py"
    f.write_text(
        "class Badint:\n"
        "    def __init__(self):\n"
        "        raise ValueError('bad init')\n"
        "    def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):\n"
        "        return None\n"
    )
    result = _run(f)
    assert result.returncode == 1
    assert "ERROR" in result.stdout
    assert "instantiation" in result.stdout.lower()


def test_missing_algo(tmp_path):
    """A player without an algo method exits 1."""
    f = tmp_path / "noalgo.py"
    f.write_text("class Noalgo:\n    pass\n")
    result = _run(f)
    assert result.returncode == 1
    assert "ERROR" in result.stdout
    assert "algo" in result.stdout.lower()


def test_missing_class(tmp_path):
    """A file with no class matching the filename exits 1."""
    f = tmp_path / "empty.py"
    f.write_text(
        "class Wrong:\n"
        "    def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):\n"
        "        return None\n"
    )
    result = _run(f)
    assert result.returncode == 1
    assert "ERROR" in result.stdout


def test_name_too_long(tmp_path):
    """A display name over the limit exits 1 (shared rule from game.validate)."""
    f = tmp_path / "toolong.py"
    f.write_text(
        "class Toolong:\n"
        "    name = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'\n"  # 26 chars, over the 25 limit
        "    def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):\n"
        "        return None\n"
    )
    result = _run(f)
    assert result.returncode == 1
    assert "ERROR" in result.stdout
    assert "exceeds" in result.stdout


def test_name_with_parens(tmp_path):
    """A display name containing parentheses exits 1."""
    f = tmp_path / "withparens.py"
    f.write_text(
        "class Withparens:\n"
        "    name = 'Bad (name)'\n"
        "    def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):\n"
        "        return None\n"
    )
    result = _run(f)
    assert result.returncode == 1
    assert "ERROR" in result.stdout
    assert "parentheses" in result.stdout


def test_real_player_alice():
    """Real player alice.py passes validation."""
    result = _run(REPO_ROOT / "players" / "alice.py")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK" in result.stdout


def test_all_real_players():
    """Every player in players/ passes validation."""
    players_dir = REPO_ROOT / "players"
    failures = []
    for player_file in sorted(players_dir.glob("*.py")):
        result = _run(player_file)
        if result.returncode != 0:
            failures.append(f"{player_file.name}: {result.stdout.strip()}")
    assert not failures, "Players failed validation:\n" + "\n".join(failures)


def test_tier_none_crash_fails_validation(tmp_path):
    """A player declaring tier that crashes when tier=None fails validation."""
    f = tmp_path / "tierbug.py"
    f.write_text(
        "class Tierbug:\n"
        "    def algo(self, hand, prior_bet, total_dice, bet_history, outcomes, tier=None):\n"
        "        return tier.upper()  # AttributeError when tier is None\n"
    )
    result = _run(f)
    assert result.returncode == 1
    assert "ERROR" in result.stdout
    assert "tier" in result.stdout.lower()


def test_valid_player_with_tier_param(tmp_path):
    """A player declaring tier=None that handles None correctly passes validation."""
    f = tmp_path / "tierok.py"
    f.write_text(
        "class Tierok:\n"
        "    def algo(self, hand, prior_bet, total_dice, bet_history, outcomes, tier=None):\n"
        "        multiplier = 0.85 if tier == 'CH' else 0.82\n"
        "        return None\n"
    )
    result = _run(f)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK" in result.stdout


def test_valid_player_with_allowed_imports(tmp_path):
    """A player using whitelisted imports (math, random, logging) passes."""
    f = tmp_path / "legit.py"
    f.write_text(
        "import random\n"
        "import logging\n"
        "from math import comb\n"
        "from game.components.bets import Bet\n"
        "\n"
        "class Legit:\n"
        "    def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):\n"
        "        return None\n"
    )
    result = _run(f)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK" in result.stdout
