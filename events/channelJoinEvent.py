from constants import clientPackets
from helpers import chatHelper as chat


def handle(userToken, packetData): # Channel join packet
    chat.joinChannel(token=userToken, channel=clientPackets.channelJoin(packetData)["channel"])
