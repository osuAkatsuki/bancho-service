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

    # Send invite
    with RedLock(
        f"{match.make_key(userToken.matchID)}:lock",
        retry_delay=50,
        retry_times=20,
    ):
        match.invite(
            multiplayer_match["match_id"],
            userToken.userID,
            clientPackets.matchInvite(rawPacketData)["userID"],
        )
