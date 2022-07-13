from constants import clientPackets
from objects.osuToken import token


def handle(userToken: token, rawPacketData: bytes):
    userToken.blockNonFriendsDM = clientPackets.blockDM(rawPacketData)["value"] > 0
