from __future__ import annotations

from constants import clientPackets
from objects import match
from objects.osuToken import Token
from objects.redisLock import redisLock


def handle(userToken: Token, rawPacketData: bytes):
    match_id = userToken["match_id"]
    if match_id is None:
        return

    packetData = clientPackets.changeSlot(rawPacketData)

    with redisLock(f"{match.make_key(match_id)}:lock"):
        multiplayer_match = match.get_match(match_id)
        if multiplayer_match is None:
            return

        match.userChangeSlot(
            multiplayer_match["match_id"],
            userToken["user_id"],
            packetData["slotID"],
        )
