from __future__ import annotations

from constants import clientPackets
from helpers import chatHelper as chat
from objects.osuToken import Token


def handle(userToken: Token, rawPacketData: bytes):
    # Send public message packet
    packetData = clientPackets.sendPublicMessage(rawPacketData)
    chat.sendMessage(
        token_id=userToken["token_id"],
        to=packetData["to"],
        message=packetData["message"],
    )
