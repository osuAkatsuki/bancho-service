from __future__ import annotations

from constants import clientPackets
from helpers import chatHelper as chat
from objects.osuToken import token


def handle(userToken: token, packetData: bytes):  # Channel join packet
    chat.partChannel(
        token=userToken,
        channel=clientPackets.channelPart(packetData)["channel"],
    )
