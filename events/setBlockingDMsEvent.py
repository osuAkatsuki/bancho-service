from constants import clientPackets


def handle(userToken, packetData):
    userToken.blockNonFriendsDM = clientPackets.blockDM(packetData)['value'] > 0
