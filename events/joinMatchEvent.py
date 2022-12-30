from __future__ import annotations

from common.log import logUtils as log
from constants import clientPackets
from constants import serverPackets
from objects import match
from objects.osuToken import token

from redlock import RedLock

def handle(userToken: token, rawPacketData: bytes):
    # read packet data
    packetData = clientPackets.joinMatch(rawPacketData)
    matchID = packetData["matchID"]
    password = packetData["password"]

    # Make sure the match exists
    multiplayer_match = match.get_match(userToken.matchID)
    if multiplayer_match is None:
        return

    # Check password
    with RedLock(
        f"{match.make_key(userToken.matchID)}:lock",
        retry_delay=50,
        retry_times=20,
    ):
        if multiplayer_match["match_password"] not in ("", password):
            userToken.enqueue(serverPackets.matchJoinFail)
            log.warning(
                f"{userToken.username} has tried to join a mp room, but he typed the wrong password.",
            )
            return

        # Password is correct, join match
        userToken.joinMatch(matchID)
