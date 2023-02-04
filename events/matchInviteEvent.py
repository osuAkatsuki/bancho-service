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

    # Send invite
    with RedLock(
        f"{match.make_key(userToken['match_id'])}:lock",
        retry_delay=100,
        retry_times=500,
    ):
        match.invite(
            multiplayer_match["match_id"],
            userToken["user_id"],
            clientPackets.matchInvite(rawPacketData)["userID"],
        )
