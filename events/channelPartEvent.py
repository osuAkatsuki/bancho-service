from __future__ import annotations

from constants import clientPackets
from helpers import chatHelper as chat
from objects.osuToken import Token


def handle(userToken: Token, packetData: bytes):
    chat.partChannel(
        token_id=userToken["token_id"],
        channel_name=clientPackets.channelPart(packetData)["channel"],
    )
