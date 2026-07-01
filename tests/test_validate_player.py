"""Tests for game/validate.py (run via python -m game.validate)."""

import subprocess
import textwrap
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


def test_init_timeout(tmp_path):
    """A player whose __init__ hangs exits 1 within the timeout."""
    f = tmp_path / "hangy.py"
    f.write_text(
        "class Hangy:\n"
        "    def __init__(self):\n"
        "        while True:\n"
        "            pass\n"
        "    def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):\n"
        "        return None\n"
    )
    result = _run(f)
    assert result.returncode == 1
    assert "ERROR" in result.stdout
    assert "timed out" in result.stdout.lower()


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


def test_v1_player_emits_deprecation_warning(tmp_path):
    """validate emits a deprecation warning for v1 algo() signatures."""
    player_src = textwrap.dedent("""
        from game.components.bets import Bet

        class Legacyplayer:
            name = "LegacyPlayer"
            def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):
                if prior_bet is None:
                    return Bet(1, 2, self.name)
                return None
    """)
    player_file = tmp_path / "legacyplayer.py"
    player_file.write_text(player_src)

    result = subprocess.run(
        ["uv", "run", "python", "-m", "game.validate", str(player_file)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert result.returncode == 0, f"validate failed: {result.stderr}"
    assert "deprecated" in result.stdout.lower() or "deprecat" in result.stderr.lower(), (
        f"Expected deprecation warning, got stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert "2026-10-05" in result.stdout or "2026-10-05" in result.stderr, (
        "Expected cutover date in deprecation warning"
    )


def test_v2_player_no_deprecation_warning(tmp_path):
    """validate does not emit a deprecation warning for v2 algo() signatures."""
    player_src = textwrap.dedent("""
        from game.components.bets import Bet

        class Modernplayer:
            name = "ModernPlayer"
            def algo(self, ctx):
                if ctx.prior_bet is None:
                    return Bet(1, 2, self.name)
                return None
    """)
    player_file = tmp_path / "modernplayer.py"
    player_file.write_text(player_src)

    result = subprocess.run(
        ["uv", "run", "python", "-m", "game.validate", str(player_file)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert result.returncode == 0, f"validate failed: {result.stderr}"
    assert "deprecat" not in result.stdout.lower()
    assert "deprecat" not in result.stderr.lower()


def test_avatar_valid_passes(tmp_path):
    """A well-formed cloud_name/public_id.ext avatar passes validation."""
    f = tmp_path / "hasavatar.py"
    f.write_text(
        "class Hasavatar:\n"
        "    avatar = 'hdyiihba/The_Merovingian_200x200_rqd12y.png'\n"
        "    def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):\n"
        "        return None\n"
    )
    result = _run(f)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK" in result.stdout


def test_avatar_missing_slash_fails(tmp_path):
    """An avatar string with no '/' separating cloud_name from public_id exits 1."""
    f = tmp_path / "badavatar.py"
    f.write_text(
        "class Badavatar:\n"
        "    avatar = 'no-slash-here'\n"
        "    def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):\n"
        "        return None\n"
    )
    result = _run(f)
    assert result.returncode == 1
    assert "ERROR" in result.stdout
    assert "avatar" in result.stdout.lower()


def test_avatar_bad_cloud_name_fails(tmp_path):
    """Uppercase or invalid characters in cloud_name exit 1."""
    f = tmp_path / "badavatar.py"
    f.write_text(
        "class Badavatar:\n"
        "    avatar = 'BadCloud/public_id.png'\n"
        "    def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):\n"
        "        return None\n"
    )
    result = _run(f)
    assert result.returncode == 1
    assert "ERROR" in result.stdout


def test_avatar_bad_public_id_fails(tmp_path):
    """Disallowed characters (e.g. a space) in public_id exit 1."""
    f = tmp_path / "badavatar.py"
    f.write_text(
        "class Badavatar:\n"
        "    avatar = 'hdyiihba/has a space.png'\n"
        "    def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):\n"
        "        return None\n"
    )
    result = _run(f)
    assert result.returncode == 1
    assert "ERROR" in result.stdout


def test_avatar_dotdot_rejected(tmp_path):
    """A '..' path segment in public_id exits 1."""
    f = tmp_path / "badavatar.py"
    f.write_text(
        "class Badavatar:\n"
        "    avatar = 'hdyiihba/../secret.png'\n"
        "    def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):\n"
        "        return None\n"
    )
    result = _run(f)
    assert result.returncode == 1
    assert "ERROR" in result.stdout


def test_avatar_disallowed_extension_fails(tmp_path):
    """An .svg extension exits 1 (raster formats only)."""
    f = tmp_path / "badavatar.py"
    f.write_text(
        "class Badavatar:\n"
        "    avatar = 'hdyiihba/public_id.svg'\n"
        "    def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):\n"
        "        return None\n"
    )
    result = _run(f)
    assert result.returncode == 1
    assert "ERROR" in result.stdout


def test_avatar_missing_extension_fails(tmp_path):
    """A public_id with no extension at all exits 1."""
    f = tmp_path / "badavatar.py"
    f.write_text(
        "class Badavatar:\n"
        "    avatar = 'hdyiihba/public_id'\n"
        "    def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):\n"
        "        return None\n"
    )
    result = _run(f)
    assert result.returncode == 1
    assert "ERROR" in result.stdout


def test_avatar_absent_is_valid(tmp_path):
    """No avatar attribute at all is perfectly valid (optional)."""
    f = tmp_path / "noavatar.py"
    f.write_text(
        "class Noavatar:\n"
        "    def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):\n"
        "        return None\n"
    )
    result = _run(f)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK" in result.stdout


def test_avatar_trailing_newline_fails(tmp_path):
    """An avatar value with a trailing newline exits 1 — '\\Z' must not match before a trailing newline."""
    f = tmp_path / "badavatar.py"
    f.write_text(
        "class Badavatar:\n"
        "    avatar = 'hdyiihba/public_id.png\\n'\n"
        "    def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):\n"
        "        return None\n"
    )
    result = _run(f)
    assert result.returncode == 1
    assert "ERROR" in result.stdout


def test_avatar_folder_nested_public_id_passes(tmp_path):
    """A public_id containing folder slashes (legal in Cloudinary) passes validation."""
    f = tmp_path / "hasavatar.py"
    f.write_text(
        "class Hasavatar:\n"
        "    avatar = 'hdyiihba/players/merovingian.png'\n"
        "    def algo(self, hand, prior_bet, total_dice, bet_history, outcomes):\n"
        "        return None\n"
    )
    result = _run(f)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK" in result.stdout
