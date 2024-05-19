from __future__ import annotations

import logging

from amplitude import BaseEvent

from common.log import logger
from constants import clientPackets
from constants import exceptions
from objects import glob
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
        targetToken = await osuToken.get_token_by_user_id(packetData["userID"])
        if targetToken is None:
            raise exceptions.tokenNotFoundException

        # Start spectating new user
        await osuToken.startSpectating(userToken["token_id"], targetToken["token_id"])

        if glob.amplitude is not None:
            glob.amplitude.track(
                BaseEvent(
                    event_type="start_spectating",
                    user_id=str(userToken["user_id"]),
                    device_id=userToken["amplitude_device_id"],
                    event_properties={
                        "host_user_id": targetToken["user_id"],
                        "host_username": targetToken["username"],
                        "host_country": targetToken["country"],
                        "host_game_mode": targetToken["game_mode"],
                        "source": "bancho-service",
                    },
                ),
            )

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
