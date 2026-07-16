from game.components.bets import Bet
from game.components.isolation import protocol as p


def test_bet_roundtrip():
    b = Bet(3, 5, "Alice")
    out = p.decode_result(p.encode_result(b))
    assert isinstance(out, Bet) and (out.quantity, out.face) == (3, 5)


def test_liar_roundtrip():
    assert p.decode_result(p.encode_result(None)) is p.LIAR


def test_error_sentinel_roundtrip():
    assert p.decode_result(p.encode_result(p.WORKER_ERROR)) is p.WORKER_ERROR
