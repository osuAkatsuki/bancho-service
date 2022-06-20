from constants import clientPackets
from objects import glob


def handle(userToken, packetData):
    with glob.matches.matches[userToken.matchID] as match: # Change slot
        match.userChangeSlot(userToken.userID, clientPackets.changeSlot(packetData)["slotID"])
