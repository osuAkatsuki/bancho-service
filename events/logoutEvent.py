from __future__ import annotations

import time

import orjson
from amplitude import BaseEvent
from cmyui.logging import Ansi
from cmyui.logging import log

import settings
from constants import serverPackets
from helpers import chatHelper as chat
from helpers import countryHelper
from objects import glob
from objects import osuToken
from objects import streamList
from objects import tokenList
from objects.osuToken import Token


async def handle(token: Token, _=None, deleteToken: bool = True):
    # Big client meme here. If someone logs out and logs in right after,
    # the old logout packet will still be in the queue and will be sent to
    # the server, so we accept logout packets sent at least 2 seconds after login
    # if the user logs out before 2 seconds, he will be disconnected later with timeout check
    if not (time.time() - token["login_time"] >= 2 or token["irc"]):
        return

    # Stop spectating
    osuToken.stopSpectating(token["token_id"])

    # Part matches
    await osuToken.leaveMatch(token["token_id"])

    # Part all joined channels
    for channel_name in osuToken.get_joined_channels(token["token_id"]):
        chat.partChannel(token_id=token["token_id"], channel_name=channel_name)

    # Leave all joined streams
    osuToken.leaveAllStreams(token["token_id"])

    # Enqueue our disconnection to everyone else
    streamList.broadcast("main", serverPackets.userLogout(token["user_id"]))

    # Disconnect from IRC if needed
    if token["irc"] and settings.IRC_ENABLE:
        glob.ircServer.forceDisconnection(token["username"])

    # Delete token
    if deleteToken:
        tokenList.deleteToken(token["token_id"])
    else:
        osuToken.update_token(
            token["token_id"],
            kicked=True,
        )

    # Change username if needed
    newUsername = glob.redis.get(
        f"ripple:change_username_pending:{token['user_id']}",
    )
    if newUsername:
        log(f"Sending username change request for {token['username']}.")
        glob.redis.publish(
            "peppy:change_username",
            orjson.dumps(
                {
                    "userID": token["user_id"],
                    "newUsername": newUsername.decode("utf-8"),
                },
            ),
        )

    # Expire token in redis
    glob.redis.expire(
        f"akatsuki:sessions:{token['token_id']}",
        60 * 60,
    )  # expire in 1 hour (60 minutes)

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
            country=countryHelper.getCountryLetters(token["country"]),
        ),
    )

    # Console output
    log(
        f"{token['username']} ({token['user_id']}) logged out. "
        f"({len(osuToken.get_token_ids()) - 1} online)",
        Ansi.LBLUE,
    )
