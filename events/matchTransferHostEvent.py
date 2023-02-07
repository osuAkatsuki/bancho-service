from __future__ import annotations

from constants import clientPackets
from objects import match
from objects.osuToken import Token

from redlock import RedLock

def handle(userToken: Token, rawPacketData: bytes):
    # Make sure we are in a match
    if userToken["match_id"] is None:
        return

    # Make sure the match exists
    multiplayer_match = match.get_match(userToken["match_id"])
    if multiplayer_match is None:
        return

    packetData = clientPackets.transferHost(rawPacketData)

    # Host check
    if userToken["user_id"] != multiplayer_match["host_user_id"]:
        return

    # Transfer host
    match.transferHost(multiplayer_match["match_id"], packetData["slotID"])
