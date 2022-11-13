from __future__ import annotations

from constants import clientPackets
from helpers import chatHelper as chat
from objects.osuToken import token


def handle(userToken: token, rawPacketData: bytes):  # Channel join packet
    chat.joinChannel(
        token=userToken,
        channel=clientPackets.channelJoin(rawPacketData)["channel"],
    )
