from __future__ import annotations

from constants import clientPackets
from helpers import chatHelper as chat
from objects.osuToken import token


def handle(userToken: token, rawPacketData):
    # Send private message packet
    packetData = clientPackets.sendPrivateMessage(rawPacketData)
    chat.sendMessage(
        token=userToken,
        to=packetData["to"],
        message=packetData["message"],
    )
