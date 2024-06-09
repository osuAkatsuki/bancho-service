from __future__ import annotations

import time

import orjson
from amplitude import BaseEvent

from common.log import logger
from constants import serverPackets
from helpers import countryHelper
from objects import glob
from objects import osuToken
from objects import stream_messages
from objects import tokenList
from objects.osuToken import Token


async def handle(
    token: Token,
    rawPacketData: bytes | None = None,
    deleteToken: bool = True,
) -> None:
    # Big client meme here. If someone logs out and logs in right after,
    # the old logout packet will still be in the queue and will be sent to
    # the server, so we accept logout packets sent at least 2 seconds after login
    # if the user logs out before 2 seconds, he will be disconnected later with timeout check
    if not (time.time() - token["login_time"] >= 2):
        return

    # Stop spectating
    if token["spectating_token_id"] is not None:
        await osuToken.stopSpectating(token["token_id"])

    # Part matches
    if token["match_id"] is not None:
        await osuToken.leaveMatch(token["token_id"])

    # Part all joined channels
    await osuToken.leaveAllChannels(token["token_id"])

    # Leave all joined streams
    await osuToken.leaveAllStreams(token["token_id"])

    # Enqueue our disconnection to everyone else
    await stream_messages.broadcast_data(
        "main",
        serverPackets.userLogout(token["user_id"]),
    )

    # Delete token
    if deleteToken:
        await tokenList.deleteToken(token["token_id"])
    else:
        await osuToken.update_token(
            token["token_id"],
            kicked=True,
        )

    # Change username if needed
    newUsername = await glob.redis.get(
        f"ripple:change_username_pending:{token['user_id']}",
    )
    if newUsername:
        assert isinstance(newUsername, bytes)

        logger.info(
            "Sending username change request",
            {
                "old_username": token["username"],
                "new_username": newUsername.decode("utf-8"),
            },
        )
        await glob.redis.publish(
            "peppy:change_username",
            orjson.dumps(
                {
                    "userID": token["user_id"],
                    "newUsername": newUsername.decode("utf-8"),
                },
            ),
        )

    if glob.amplitude is not None:
        glob.amplitude.track(
            BaseEvent(
                event_type="osu_logout",
                user_id=str(token["user_id"]),
                device_id=token["amplitude_device_id"],
                event_properties={
                    "username": token["username"],
                    "session_duration": time.time() - token["login_time"],
                    "login_time": token["login_time"],
                    "source": "bancho-service",
                },
                location_lat=token["latitude"],
                location_lng=token["longitude"],
                ip=token["ip"],
                country=countryHelper.osu_code_to_iso_code(token["country"]),
            ),
        )

    # Console output
    logger.info(
        "User signed out",
        extra={
            "user_id": token["user_id"],
            "username": token["username"],
            "ip": token["ip"],
        },
    )
