from __future__ import annotations

from constants import clientPackets
from objects import match
from objects.osuToken import Token

from redlock import RedLock

def handle(userToken: Token, rawPacketData: bytes):
    match_id = userToken["match_id"]
    if match_id is None:
        return

    multiplayer_match = match.get_match(match_id)
    if multiplayer_match is None:
        return

    packetData = clientPackets.changeSlot(rawPacketData)

    match.userChangeSlot(
        multiplayer_match["match_id"],
        userToken["user_id"],
        packetData["slotID"],
    )
