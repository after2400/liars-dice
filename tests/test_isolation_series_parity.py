"""Task 10 parity test: run_series's isolated worker-pool path must produce
identical results to the in-process path across a MULTI-game series.

A single-game test (Task 9's test_isolation_orchestrator_parity.py) can't
exercise the failure mode that only shows up across a series:
game_orchestrator shuffles `players` in place every game
(`rng.shuffle(players)` in script.py), so a WorkerPool must route turns by
player *name* (`pool.name_to_index`, fixed at construction), never by a live
list position — get that wrong and games after the first would route a turn
to the wrong player's worker.

The two bots are also both v2 (`algo(self, ctx)`) and read `ctx.bet_history`
to decide whether to call liar, so this test doubles as a regression guard on
`run_series` actually wiring `WorkerConfig.readmodel_name` to the series'
`ReadModelWriter` — if that wiring were dropped, the isolated bots would see
an always-empty `ctx.bet_history` and diverge from the in-process run.

import_player_classes_from_dir requires each player's filename stem to match
its class name (case-insensitively), hence two tiny temp files rather than
inline classes.

Security note (Task 15): import_player_classes_from_dir now returns
lightweight "shell" objects whose .algo() is a stub that only exists to
satisfy inspect.signature() — the real class is never imported or
instantiated in the parent process, precisely so a real bot's untrusted
__init__/algo() can never run unscrubbed here. That means the loader's
return value can no longer be used to actually PLAY a game in-process
(isolated=False) — only the isolated leg (which reloads the real class
inside a scrubbed worker, keyed off `_isolation_spec`) can. The in-process
leg below therefore loads the real classes directly via plain importlib,
bypassing the security loader entirely — legitimate here because these are
trusted, test-authored fixture files, not arbitrary bot code, and this is a
test of engine parity, not a production roster load.
"""

import importlib.util

from game.components.series import run_series
from game.components.utils import import_player_classes_from_dir

_BOT_CLASS_NAMES = {"historybota": "HistoryBotA", "historybotb": "HistoryBotB"}


def _load_real_players_directly(tmp_path):
    """Bypass the security loader and construct real player instances
    directly, for the in-process comparison leg only (see module docstring)."""
    players = []
    for stem, class_name in _BOT_CLASS_NAMES.items():
        path = tmp_path / f"{stem}.py"
        spec = importlib.util.spec_from_file_location(stem, str(path))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        players.append(getattr(module, class_name)())
    return players


REPLAY_SEEDS = [101, 202, 303]

# Both bots run the identical strategy: open with a fixed bid if acting first
# in a round, otherwise call liar -- deterministic and guaranteed to resolve
# every round in exactly two turns, regardless of which of the two players the
# per-game shuffle picks to act first. The "else: raise" branch only fires if
# ctx.bet_history was NOT populated (i.e. the read-model wiring is broken),
# which would cause the isolated and in-process runs to diverge (different
# game lengths / winners) instead of silently passing.
_BOT_SRC = """
from game.components.bets import Bet


class {class_name}:
    name = "unnamed"

    def algo(self, ctx):
        if ctx.prior_bet is None:
            return Bet(2, 3, self.name)
        if len(ctx.bet_history) > 0:
            return None
        return Bet(ctx.prior_bet.quantity + 1, ctx.prior_bet.face, self.name)
"""


def _write_bots(tmp_path):
    (tmp_path / "historybota.py").write_text(_BOT_SRC.format(class_name="HistoryBotA"))
    (tmp_path / "historybotb.py").write_text(_BOT_SRC.format(class_name="HistoryBotB"))


def test_isolated_and_in_process_series_produce_identical_results(tmp_path):
    _write_bots(tmp_path)

    in_process_players = _load_real_players_directly(tmp_path)
    for p in in_process_players:
        p.name = type(p).__name__
    in_process_result = run_series(
        in_process_players,
        n_games=3,
        replay_seeds=list(REPLAY_SEEDS),
        capture_outcomes=True,
        isolated=False,
    )

    isolated_players = import_player_classes_from_dir(str(tmp_path))
    for p in isolated_players:
        p.name = type(p).__name__
    isolated_result = run_series(
        isolated_players,
        n_games=3,
        replay_seeds=list(REPLAY_SEEDS),
        capture_outcomes=True,
        isolated=True,
        worker_timeout_s=5.0,
    )

    assert in_process_result.wins == isolated_result.wins
    # Sanity: the read-model wiring worked and the "history not wired" branch
    # never fired -- every round resolved in exactly two turns, so total wins
    # across both bots equals the number of games played.
    assert sum(in_process_result.wins.values()) == 3

    assert in_process_result.stats.snapshot_state() == isolated_result.stats.snapshot_state()

    assert len(in_process_result.outcomes) == len(isolated_result.outcomes)
    for expected, actual in zip(in_process_result.outcomes, isolated_result.outcomes):
        assert expected["round"] == actual["round"]
        assert expected["bidder"] == actual["bidder"]
        assert expected["challenger"] == actual["challenger"]
        assert expected["bet_held"] == actual["bet_held"]
        assert expected["loser"] == actual["loser"]
        assert dict(expected["hands"]) == dict(actual["hands"])


def test_run_series_isolated_requires_players_loaded_via_loader():
    """A player constructed directly (bypassing the loader) has no
    `_isolation_spec`, so isolated=True must fail loudly rather than guess at
    a source file or silently fall back to in-process."""
    import pytest

    class NotLoadedViaDir:
        name = "NotLoadedViaDir"

        def algo(self, ctx):
            return None

    with pytest.raises(ValueError, match="_isolation_spec"):
        run_series([NotLoadedViaDir(), NotLoadedViaDir()], n_games=1, isolated=True)
