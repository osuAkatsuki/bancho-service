from __future__ import annotations

from constants import clientPackets
from helpers import chatHelper as chat
from objects.osuToken import Token


def handle(userToken: Token, rawPacketData):
    # Send private message packet
    packetData = clientPackets.sendPrivateMessage(rawPacketData)
    chat.sendMessage(
        token_id=userToken["token_id"],
        to=packetData["to"],
        message=packetData["message"],
    )
