from constants import clientPackets
from objects import glob


def handle(userToken, packetData):
    # Read packet data. Same structure as changeMatchSettings
    packetData = clientPackets.changeMatchSettings(packetData)

    # Make sure the match exists
    if userToken.matchID not in glob.matches.matches:
        return

    with glob.matches.matches[userToken.matchID] as match:
        # Host check
        if userToken.userID != match.hostUserID:
            return

        # Update match password
        match.changePassword(packetData["matchPassword"])
