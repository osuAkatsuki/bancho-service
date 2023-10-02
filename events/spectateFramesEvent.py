from __future__ import annotations

import logging

from constants import serverPackets
from objects import stream
from objects import streamList
from objects.osuToken import Token


async def handle(userToken: Token, rawPacketData: bytes):
    # Send spectator frames to every spectator
    streamName = f"spect/{userToken['user_id']}"
    await streamList.broadcast(
        streamName,
        serverPackets.spectatorFrames(rawPacketData[7:]),
    )

    logging.debug(
        "Broadcasting osu! spectator frames",
        extra={
            "host_user_id": userToken["user_id"],
            "num_clients": stream.getClientCount(streamName),
        },
    )
