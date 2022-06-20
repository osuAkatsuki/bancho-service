from constants import clientPackets
from objects import glob


def handle(userToken, packetData):
    # Make sure we are in a match
    if userToken.matchID == -1:
        return

    # Make sure the match exists
    if userToken.matchID not in glob.matches.matches:
        return

    # Host check
    with glob.matches.matches[userToken.matchID] as match:
        if userToken.userID != match.hostUserID:
            return

        # Transfer host
        match.transferHost(clientPackets.transferHost(packetData)["slotID"])
