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


def test_import_crash(tmp_path):
    """A file that raises on import exits 1."""
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
    assert "import" in result.stdout.lower()


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
    """A file with no matching class exits 1."""
    f = tmp_path / "empty.py"
    f.write_text("x = 1\n")
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
