from constants import clientPackets, serverPackets
from objects import glob


def handle(userToken, packetData):
    # Make sure we are in a match
    if userToken.matchID == -1:
        return

    # Make sure the match exists
    if userToken.matchID not in glob.matches.matches:
        return

    # Parse the data
    data = clientPackets.matchFrames(packetData)

    with glob.matches.matches[userToken.matchID] as match:
        # Change slot id in packetData
        slotID = match.getUserSlotID(userToken.userID)

        # Update the score
        match.updateScore(slotID, data["totalScore"])
        match.updateHP(slotID, data["currentHp"])

        # Enqueue frames to who's playing
        glob.streams.broadcast(match.playingStreamName, serverPackets.matchFrames(slotID, packetData))
