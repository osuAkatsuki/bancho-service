from __future__ import annotations

import logging

from common.log import logger
from constants import clientPackets
from constants import exceptions
from objects import osuToken
from objects.osuToken import Token


async def handle(userToken: Token, rawPacketData: bytes) -> None:
    try:
        # Start spectating packet
        packetData = clientPackets.startSpectating(rawPacketData)
    except:
        logger.warning("Failed to parse start spectating packet.")
        return

    try:
        # If the user id is less than 0, treat this as a stop spectating packet
        if packetData["userID"] < 0:
            logging.warning(
                "Received a negative user id in start spectating packet.",
                extra={
                    "user_id": userToken["user_id"],
                    "host_user_id": packetData["userID"],
                },
            )
            await osuToken.stopSpectating(userToken["token_id"])
            return

        # Get host token
        targetToken = await osuToken.get_primary_token_by_user_id(packetData["userID"])
        if targetToken is None:
            raise exceptions.tokenNotFoundException

        # Start spectating new user
        await osuToken.startSpectating(userToken["token_id"], targetToken["token_id"])

    except exceptions.tokenNotFoundException:
        # Stop spectating if token not found
        logger.warning(
            "Spectator start: token not found.",
            extra={
                "user_id": userToken["user_id"],
                "host_user_id": packetData["userID"],
            },
        )
        await osuToken.stopSpectating(userToken["token_id"])
