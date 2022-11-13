from __future__ import annotations

import re
import threading
from queue import Queue
from time import time
from typing import Optional
from typing import TypedDict

from common.constants import actions
from common.ripple import userUtils
from constants import fokabotCommands
from constants import serverPackets
from objects import glob

# Some common regexes, compiled to increase performance.
reportRegex = re.compile(r"^(.+) \((.+)\)\:(?: )?(.+)?$")
usernameRegex = re.compile(r"^[\w \[\]-]{2,15}$")
npRegex = re.compile(
    r"^https?://osu\.(?:akatsuki\.pw|akatest\.space|ppy\.sh)/beatmapsets/"
    r"(?P<set_id>\d{1,10})/?#/?"
    r"(?P<mode>osu|taiko|fruits|mania)?/?"
    r"(?P<id>\d{1,10})/?$",
)


def connect() -> None:
    with glob.tokens:
        token = glob.tokens.addToken(999)

    token.actionID = actions.IDLE
    glob.streams.broadcast("main", serverPackets.userPanel(999))
    glob.streams.broadcast("main", serverPackets.userStats(999))


def disconnect() -> None:
    with glob.tokens:
        token = glob.tokens.getTokenFromUserID(999)
        assert token is not None

        glob.tokens.deleteToken(token)


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

        # If this is an !mp command in a match, make sure the user is a referee.
        if chan.startswith("#multi_") and cmd["trigger"] == "!mp":
            match = glob.matches.getMatchFromChannel(chan)
            assert match is not None

            if not match.is_referee(userID):
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
            queue = Queue()
            thread = threading.Thread(
                target=lambda q, arg1, arg2, arg3: q.put(
                    handle_command(cmd, arg1, arg2, arg3),
                ),
                args=(queue, fro, chan, message_split[1:]),
                daemon=True,
            )
            thread.start()
            thread.join()

            resp = queue.get()

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
