from __future__ import annotations

from common.log import logUtils as log
from constants import clientPackets
from constants import serverPackets
from objects import match, osuToken
from objects.osuToken import Token

from redlock import RedLock

def handle(userToken: Token, rawPacketData: bytes):
    # read packet data
    packetData = clientPackets.joinMatch(rawPacketData)
    matchID = packetData["matchID"]
    password = packetData["password"]

    # Make sure the match exists
    multiplayer_match = match.get_match(matchID)
    if multiplayer_match is None:
        osuToken.enqueue(userToken["token_id"], serverPackets.matchJoinFail)
        return

    # Check password
    with RedLock(
        f"{match.make_key(matchID)}:lock",
        retry_delay=100,
        retry_times=500,
    ):
        if multiplayer_match["match_password"] not in ("", password):
            osuToken.enqueue(userToken["token_id"], serverPackets.matchJoinFail)
            log.warning(
                f"{userToken['username']} has tried to join a mp room, but he typed the wrong password.",
            )
            return

        # Password is correct, join match
        osuToken.joinMatch(userToken["token_id"], matchID)
