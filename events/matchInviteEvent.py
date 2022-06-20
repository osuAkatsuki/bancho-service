from constants import clientPackets
from objects import glob


def handle(userToken, packetData):
    # Make sure we are in a match
    if userToken.matchID == -1:
        return

    # Make sure the match exists
    if userToken.matchID not in glob.matches.matches:
        return

    # Send invite
    with glob.matches.matches[userToken.matchID] as match:
        match.invite(userToken.userID, clientPackets.matchInvite(packetData)["userID"])
