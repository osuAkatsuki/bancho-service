from common.ripple import userUtils
from constants import clientPackets


def handle(userToken, packetData): # Friend add packet
    userUtils.addFriend(userToken.userID, clientPackets.addRemoveFriend(packetData)["friendID"])
