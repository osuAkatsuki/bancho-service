from __future__ import annotations

from constants import clientPackets
from objects import match
from objects.osuToken import Token
from objects.redisLock import redisLock


def handle(userToken: Token, rawPacketData: bytes):
    # Read packet data. Same structure as changeMatchSettings
    packetData = clientPackets.changeMatchSettings(rawPacketData)

    match_id = userToken["match_id"]
    if match_id is None:
        return

    # Make sure the match exists
    multiplayer_match = match.get_match(match_id)
    if multiplayer_match is None:
        return

    with redisLock(f"{match.make_key(match_id)}:lock"):
        # Host check
        if match_id != multiplayer_match["host_user_id"]:
            return

        # Update match password
        match.changePassword(multiplayer_match["match_id"], packetData["matchPassword"])
