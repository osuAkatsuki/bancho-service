from __future__ import annotations

import time

import orjson
from cmyui.logging import Ansi
from cmyui.logging import log

import settings
from constants import serverPackets
from helpers import chatHelper as chat
from objects import glob


def handle(userToken, _=None, deleteToken=True):
    # Big client meme here. If someone logs out and logs in right after,
    # the old logout packet will still be in the queue and will be sent to
    # the server, so we accept logout packets sent at least 2 seconds after login
    # if the user logs out before 2 seconds, he will be disconnected later with timeout check
    if time.time() - userToken.loginTime >= 2 or userToken.irc:
        # Stop spectating
        userToken.stopSpectating()

        # Part matches
        userToken.leaveMatch()

        # Part all joined channels
        for i in userToken.joinedChannels:
            chat.partChannel(token=userToken, channel=i)

        # Leave all joined streams
        userToken.leaveAllStreams()

        # Enqueue our disconnection to everyone else
        glob.streams.broadcast("main", serverPackets.userLogout(userToken.userID))

        # Disconnect from IRC if needed
        if userToken.irc and settings.IRC_ENABLE:
            glob.ircServer.forceDisconnection(userToken.username)

        # Delete token
        if deleteToken:
            glob.tokens.deleteToken(userToken.token)
        else:
            userToken.kicked = True

        # Change username if needed
        newUsername = glob.redis.get(
            f"ripple:change_username_pending:{userToken.userID}",
        )
        if newUsername:
            log(f"Sending username change request for {userToken.username}.")
            glob.redis.publish(
                "peppy:change_username",
                orjson.dumps(
                    {
                        "userID": userToken.userID,
                        "newUsername": newUsername.decode("utf-8"),
                    },
                ),
            )

        # Expire token in redis
        glob.redis.expire(
            f"akatsuki:sessions:{userToken.token}",
            60 * 60,
        )  # expire in 1 hour (60 minutes)

        # Console output
        log(
            f"{userToken.username} ({userToken.userID}) logged out. "
            f"({len(glob.tokens.tokens) - 1} online)",
            Ansi.LBLUE,
        )
