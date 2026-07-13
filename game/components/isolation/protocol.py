"""Fixed-shape encoding for the per-turn result path (worker -> parent).

The result is tiny and fixed-schema, so we struct-pack it rather than pickle:
tag byte + two uint16 (quantity, face). The `player` field of a returned Bet is
set by the parent from the known acting player, so it need not cross the wire.
"""

import struct

LIAR = object()  # player called liar (algo returned None)
WORKER_ERROR = object()  # bot raised / crashed / timed out -> penalise

_TAG_BET, _TAG_LIAR, _TAG_ERROR = 0, 1, 2
_FMT = "<BHH"  # tag, quantity, face


def encode_result(action) -> bytes:
    from game.components.bets import Bet

    if action is None:
        return struct.pack(_FMT, _TAG_LIAR, 0, 0)
    if action is WORKER_ERROR:
        return struct.pack(_FMT, _TAG_ERROR, 0, 0)
    if isinstance(action, Bet):
        return struct.pack(_FMT, _TAG_BET, int(action.quantity), int(action.face))
    raise TypeError(f"cannot encode result of type {type(action).__name__}")


def decode_result(data: bytes):
    from game.components.bets import Bet

    tag, quantity, face = struct.unpack(_FMT, data)
    if tag == _TAG_LIAR:
        return LIAR
    if tag == _TAG_ERROR:
        return WORKER_ERROR
    return Bet(quantity, face, None)  # parent fills in player identity
