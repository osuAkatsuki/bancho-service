from __future__ import annotations

from constants import clientPackets
from objects import glob
from objects.osuToken import token


def handle(userToken: token, rawPacketData: bytes):
    # Make sure we are in a match
    if userToken.matchID == -1:
        return

    # Make sure the match exists
    if userToken.matchID not in glob.matches.matches:
        return

    # Send invite
    with glob.matches.matches[userToken.matchID] as match:
        match.invite(
            userToken.userID,
            clientPackets.matchInvite(rawPacketData)["userID"],
        )
