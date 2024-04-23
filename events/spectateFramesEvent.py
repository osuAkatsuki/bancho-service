from __future__ import annotations

import time

from common.log import logger
from constants import serverPackets
from objects import streamList
from objects.osuToken import Token


async def handle(userToken: Token, rawPacketData: bytes):
    st = time.perf_counter_ns()
    # Send spectator frames to every spectator
    streamName = f"spect/{userToken['user_id']}"
    await streamList.broadcast(
        streamName,
        serverPackets.spectatorFrames(rawPacketData[7:]),
        but=[userToken["token_id"]],
    )

    logger.debug(
        "Broadcasting osu! spectator frames",
        extra={"user_id": userToken["user_id"]},
    )
    logger.info(
        f"Completed spectator frame packet in {(time.perf_counter_ns()-st)/1000} microseconds",
        extra={"user_id": userToken["user_id"]},
    )
