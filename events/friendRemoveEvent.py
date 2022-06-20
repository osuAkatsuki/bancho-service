from common.ripple import userUtils
from constants import clientPackets


def handle(userToken, packetData): # Friend remove packet
    userUtils.removeFriend(userToken.userID, clientPackets.addRemoveFriend(packetData)["friendID"])
