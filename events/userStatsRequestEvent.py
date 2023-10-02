from __future__ import annotations

from common.log import logger
from constants import clientPackets
from constants import serverPackets
from objects import osuToken
from objects.osuToken import Token


async def handle(userToken: Token, rawPacketData: bytes):
    # Read userIDs list
    packetData = clientPackets.userStatsRequest(rawPacketData)

    # Process lists with length <= 32
    if len(packetData) > 32:
        logger.warning("Received userStatsRequest with length > 32.")
        return

    for userID in packetData["users"]:
        logger.debug("Sending stats for user", extra={"user_id": userID})

        # Skip our stats
        if userID == userToken["user_id"]:
            continue

        # Enqueue stats packets relative to this user
        await osuToken.enqueue(
            userToken["token_id"],
            await serverPackets.userStats(userID),
        )
