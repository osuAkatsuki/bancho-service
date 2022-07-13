from constants import clientPackets
from objects import glob
from objects.osuToken import token


def handle(userToken: token, rawPacketData: bytes):
    with glob.matches.matches[userToken.matchID] as match:  # Change slot
        match.userChangeSlot(
            userToken.userID, clientPackets.changeSlot(rawPacketData)["slotID"]
        )
