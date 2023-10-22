from __future__ import annotations

import logging

from constants import clientPackets
from constants import serverPackets
from objects import osuToken
from objects.osuToken import Token


async def handle(userToken: Token, rawPacketData: bytes):
    # Read userIDs list
    packetData = clientPackets.userStatsRequest(rawPacketData)

    # Process lists with length <= 32
    if len(packetData) > 32:
        logging.warning("Received userStatsRequest with length > 32.")
        return

    for other_id in packetData["users"]:
        logging.debug("Sending stats for user", extra={"user_id": other_id})

        # Skip our stats
        if other_id == userToken["user_id"]:
            continue

        other_token = await osuToken.get_token_by_user_id(user_id=other_id)
        if other_token is None:
            continue

        # Enqueue stats packets relative to this user
        await osuToken.enqueue(
            userToken["token_id"],
            await serverPackets.userStats(other_token),
        )
