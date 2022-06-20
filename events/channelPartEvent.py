from constants import clientPackets
from helpers import chatHelper as chat


def handle(userToken, packetData): # Channel join packet
    chat.partChannel(token=userToken, channel=clientPackets.channelPart(packetData)["channel"])
