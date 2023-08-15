from __future__ import annotations

from amplitude import BaseEvent

from common.log import logUtils as log
from constants import clientPackets
from constants import exceptions
from objects import glob
from objects import osuToken
from objects import tokenList
from objects.osuToken import Token


def handle(userToken: Token, rawPacketData: bytes):
    try:
        # Start spectating packet
        packetData = clientPackets.startSpectating(rawPacketData)

        # If the user id is less than 0, treat this as a stop spectating packet
        if packetData["userID"] < 0:
            osuToken.stopSpectating(userToken["token_id"])
            return

        # Get host token
        targetToken = tokenList.getTokenFromUserID(packetData["userID"])
        if targetToken is None:
            raise exceptions.tokenNotFoundException

        # Start spectating new user
        osuToken.startSpectating(userToken["token_id"], targetToken["token_id"])

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
        log.warning("Spectator start: token not found.")
        osuToken.stopSpectating(userToken["token_id"])
