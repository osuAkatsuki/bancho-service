from constants import clientPackets
from helpers import chatHelper as chat
from objects.osuToken import token


def handle(userToken: token, rawPacketData: bytes):
    # Send public message packet
    packetData = clientPackets.sendPublicMessage(rawPacketData)
    chat.sendMessage(
        token=userToken,
        to=packetData["to"],
        message=packetData["message"],
    )
