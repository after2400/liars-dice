"""Tests for game/validate.py's Phase 2 isolated instantiate-and-probe step
(Task 11: replaces in-process importlib.exec_module + SIGALRM-guarded
instantiation with a WorkerPool worker -- same primitive already used to run
untrusted player code during real games).

Run via the same `uv run python -m game.validate <file>` subprocess pattern
as tests/test_validate_player.py.
"""

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


def test_benign_v2_bot_passes_isolated_probe(tmp_path):
    """A well-formed v2 bot passes both the AST phase and the isolated Phase 2
    instantiate-and-probe (WorkerPool spawns a worker, instantiates the
    class, and runs one empty-history algo() call)."""
    f = tmp_path / "goodbot.py"
    f.write_text("class Goodbot:\n    def algo(self, ctx):\n        return None\n")
    result = _run(f)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK" in result.stdout


def test_benign_v2_bot_ignoring_tier_gets_probed(tmp_path):
    """The isolated probe call is unconditional for every bot, regardless of
    whether it reads ctx.tier -- passing confirms the probe ran (with an
    empty-history GameContext) and didn't choke on a bot that never touches
    ctx.tier."""
    f = tmp_path / "untiered.py"
    f.write_text("class Untiered:\n    def algo(self, ctx):\n        return None\n")
    result = _run(f)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK" in result.stdout


def test_v2_bot_that_crashes_in_algo_is_rejected(tmp_path):
    """The isolated probe actually calls algo() -- a bot whose algo() always
    raises must be rejected, not just imported and instantiated."""
    f = tmp_path / "buggyalgo.py"
    f.write_text("class Buggyalgo:\n    def algo(self, ctx):\n        raise ValueError('boom')\n")
    result = _run(f)
    assert result.returncode == 1
    assert "ERROR" in result.stdout


def test_algo_hang_rejected_by_isolated_probe(tmp_path):
    """A bot whose algo() hangs forever is rejected within the timeout by a
    real process kill() (WorkerPool), not the old SIGALRM handler (which
    can't interrupt a blocking native/C-level call). This genuinely takes
    ~10s (the probe timeout) -- no test-only override was added to
    validate.py's CLI entry point, so this test pays that cost directly."""
    f = tmp_path / "hangybot.py"
    f.write_text(
        "class Hangybot:\n    def algo(self, ctx):\n        while True:\n            pass\n"
    )
    result = _run(f)
    assert result.returncode == 1
    assert "ERROR" in result.stdout
    assert "timed out" in result.stdout.lower()


def test_secret_reading_bot_rejected_at_ast_phase(tmp_path):
    """A bot that tries to read a planted secret via os.environ is rejected
    at Phase 1 (blocked import) before it ever reaches the isolated Phase 2
    probe -- Phase 1's import whitelist blocks `import os` outright.

    This does not re-prove environment-scrubbing confinement of the isolated
    worker itself; that has dedicated regression coverage in
    tests/test_isolation_confinement.py (test_worker_cannot_read_planted_secret).
    This test's job is only to confirm validate.py's gate still rejects the
    attempt end-to-end.
    """
    f = tmp_path / "secretpeeker.py"
    f.write_text(
        "import os\n"
        "\n"
        "class Secretpeeker:\n"
        "    def algo(self, ctx):\n"
        "        return os.environ.get('GH_TOKEN')\n"
    )
    result = _run(f)
    assert result.returncode == 1
    assert "ERROR" in result.stdout
    assert "not allowed" in result.stdout.lower()
