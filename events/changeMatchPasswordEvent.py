from __future__ import annotations

from constants import clientPackets
from objects import glob
from objects.osuToken import token


def handle(userToken: token, rawPacketData: bytes):
    # Read packet data. Same structure as changeMatchSettings
    packetData = clientPackets.changeMatchSettings(rawPacketData)

    # Make sure the match exists
    if userToken.matchID not in glob.matches.matches:
        return

    with glob.matches.matches[userToken.matchID] as match:
        # Host check
        if userToken.userID != match.hostUserID:
            return

        # Update match password
        match.changePassword(packetData["matchPassword"])
