from __future__ import annotations

import re
from time import time
from typing import Optional
from typing import TypedDict

from common.constants import actions
from common.ripple import userUtils
from constants import fokabotCommands
from constants import serverPackets
from objects import channelList
from objects import osuToken
from objects import streamList
from objects import tokenList
from objects.redisLock import redisLock

REPORT_REGEX = re.compile(r"^(.+) \((.+)\)\:(?: )?(.+)?$")

USERNAME_REGEX = re.compile(r"^[\w \[\]-]{2,15}$")

NOW_PLAYING_REGEX = re.compile(
    r"^(?P<action_type>playing|editing|watching|listening to) "
    rf"\[https://osu\.(?:akatsuki\.pw|akatsuki\.gg|akatest\.space|ppy\.sh)/beatmapsets/"
    rf"(?P<sid>\d{{1,10}})#/?(?:osu|taiko|fruits|mania)?/(?P<bid>\d{{1,10}})/? .+\]"
    r"(?: <(?P<mode_vn>Taiko|CatchTheBeat|osu!mania)>)?"
    # TODO: don't include the space at the start of mods
    r"(?P<mods>(?: (?:-|\+|~|\|)\w+(?:~|\|)?)+)?\x01$",
)


def connect() -> None:
    with redisLock(f"bancho:locks:aika"):
        token = tokenList.getTokenFromUserID(999)
        if token is not None:
            return

        token = tokenList.addToken(999)
        assert token is not None

        osuToken.update_token(token["token_id"], action_id=actions.IDLE)
        streamList.broadcast("main", serverPackets.userPanel(999))
        streamList.broadcast("main", serverPackets.userStats(999))

        for channel_name in channelList.getChannelNames():
            osuToken.joinChannel(token["token_id"], channel_name)


def disconnect() -> None:
    with redisLock(f"bancho:locks:aika"):
        token = tokenList.getTokenFromUserID(999)
        assert token is not None

        tokenList.deleteToken(token["token_id"])


# def reload_commands():
# 	"""Reloads the Fokabot commands module."""
#     # NOTE: this is not safe, will break references
# 	reload(fokabotCommands)


class CommandResponse(TypedDict):
    response: str
    hidden: bool


def fokabotResponse(fro: str, chan: str, message: str) -> Optional[CommandResponse]:
    """
    Check if a message has triggered FokaBot

    :param fro: sender username
    :param chan: channel name (or receiver username)
    :param message: chat mesage (recieved to this function as a string, but we split into list[str] for commands)
    :return: FokaBot's response or False if no response
    """

    start_time = time()
    message = message.strip()

    for rgx, cmd in fokabotCommands._commands:
        if not rgx.match(message):
            continue

        # message has triggered a command
        userID = userUtils.getID(fro)

        # Make sure the user has right permissions
        if (
            cmd["privileges"]
            and not userUtils.getPrivileges(userID) & cmd["privileges"]
        ):
            return None

        # Check argument number
        message_split = message.split(" ")
        if cmd["syntax"] and len(message_split) <= cmd["syntax"].count(" ") + 1:
            return {
                "response": f'Incorrect syntax: {cmd["trigger"]} {cmd["syntax"]}',
                "hidden": True,
            }

        def handle_command(cmd, fro, chan, msg):
            try:
                resp = cmd["callback"](fro, chan, msg)
            except Exception as e:
                return e

            return resp

        if cmd["callback"]:
            resp = handle_command(cmd, fro, chan, message_split[1:])

            if isinstance(resp, Exception):
                raise resp
        else:
            resp = cmd["response"]

        if not resp:
            return None

        resp = [resp]
        if userID == 1001:
            resp.append(f"Elapsed: {(time() - start_time) * 1000:.3f}ms")

        return {"response": " | ".join(resp), "hidden": cmd["hidden"]}

    # No commands triggered
    return None
