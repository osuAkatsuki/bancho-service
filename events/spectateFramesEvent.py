from __future__ import annotations

from common.log import logger
from constants import serverPackets
from objects import streamList
from objects.osuToken import Token


async def handle(userToken: Token, rawPacketData: bytes) -> None:
    # Send spectator frames to every spectator
    streamName = f"spect/{userToken['user_id']}"
    await streamList.broadcast(
        streamName,
        serverPackets.spectatorFrames(rawPacketData[7:]),
        excluded_token_ids=[userToken["token_id"]],
    )

    logger.debug(
        "Broadcasting osu! spectator frames",
        extra={"user_id": userToken["user_id"]},
    )
