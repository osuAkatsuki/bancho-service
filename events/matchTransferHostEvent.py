from __future__ import annotations

from constants import clientPackets
from objects import match
from objects.osuToken import token

from redlock import RedLock

def handle(userToken: token, rawPacketData: bytes):
    # Make sure we are in a match
    if userToken.matchID == -1:
        return

    # Make sure the match exists
    multiplayer_match = match.get_match(userToken.matchID)
    if multiplayer_match is None:
        return

    packetData = clientPackets.transferHost(rawPacketData)

    # Host check
    with RedLock(
        f"{match.make_key(userToken.matchID)}:lock",
        retry_delay=50,
        retry_times=20,
    ):
        if userToken.userID != multiplayer_match["host_user_id"]:
            return

        # Transfer host
        match.transferHost(multiplayer_match["match_id"], packetData["slotID"])
