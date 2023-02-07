from __future__ import annotations

from constants import clientPackets
from helpers import chatHelper as chat
from objects.osuToken import Token


def handle(userToken: Token, rawPacketData: bytes):  # Channel join packet
    chat.joinChannel(
        token_id=userToken["token_id"],
        channel_name=clientPackets.channelJoin(rawPacketData)["channel"],
    )
