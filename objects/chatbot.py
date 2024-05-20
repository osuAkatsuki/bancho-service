from __future__ import annotations

import re
from time import time
from typing import TypedDict

from amplitude import BaseEvent

from common.constants import actions
from common.constants import privileges
from common.log import logger
from common.ripple import user_utils
from constants import CHATBOT_USER_ID
from constants import chatbotCommands
from constants import serverPackets
from objects import channelList
from objects import glob
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


async def connect() -> None:
    async with redisLock(f"bancho:locks:aika"):
        token = await osuToken.get_token_by_user_id(CHATBOT_USER_ID)
        if token is not None:
            return

        token = await tokenList.addToken(CHATBOT_USER_ID)
        assert token is not None

        await osuToken.update_token(token["token_id"], action_id=actions.IDLE)
        await streamList.broadcast(
            "main",
            await serverPackets.userPanel(CHATBOT_USER_ID),
        )
        await streamList.broadcast(
            "main",
            await serverPackets.userStats(CHATBOT_USER_ID),
        )

        for channel_name in await channelList.getChannelNames():
            await osuToken.joinChannel(token["token_id"], channel_name)


async def disconnect() -> None:
    async with redisLock(f"bancho:locks:aika"):
        token = await osuToken.get_token_by_user_id(CHATBOT_USER_ID)
        assert token is not None

        await tokenList.deleteToken(token["token_id"])


class ChatbotResponse(TypedDict):
    response: str
    hidden: bool


COMMANDS_MAP = {
    re.compile(f"^{cmd['trigger']}( (.+)?)?$"): cmd for cmd in chatbotCommands.commands
}.items()


async def query(
    fro: str,
    chan: str,
    message: str,
) -> ChatbotResponse | None:
    """
    Check if a message has triggered chatbot

    :param fro: sender username
    :param chan: channel name (or receiver username)
    :param message: chat mesage (recieved to this function as a string, but we split into list[str] for commands)
    :return: chatbot's response or False if no response
    """

    start_time = time()
    message = message.strip()

    for rgx, cmd in COMMANDS_MAP:
        if not rgx.match(message):
            continue

        # message has triggered a command
        user_token = await osuToken.get_token_by_username(fro)
        if user_token is None:
            logger.warning(
                "An offline user attempted to use a chatbot command",
                extra={"username": fro},
            )
            return None

        # Make sure the user has right permissions
        if cmd["privileges"] and not user_token["privileges"] & cmd["privileges"]:
            return None

        # Check argument number
        message_split = message.split(" ")
        if cmd["syntax"] and len(message_split) <= cmd["syntax"].count(" ") + 1:
            return {
                "response": f'Incorrect syntax: {cmd["trigger"]} {cmd["syntax"]}',
                "hidden": True,
            }

        command_response = await cmd["callback"](fro, chan, message_split[1:])
        if not command_response:
            return None

        time_elapsed_ms = (time() - start_time) * 1000

        if user_token["privileges"] & privileges.ADMIN_CAKER:
            command_response += f"| Elapsed: {(time() - start_time) * 1000:.3f}ms"

        if glob.amplitude is not None:
            glob.amplitude.track(
                BaseEvent(
                    event_type="chatbot_command_invocation",
                    user_id=str(user_token["user_id"]),
                    device_id=user_token["amplitude_device_id"],
                    event_properties={
                        "command": cmd["trigger"],
                        "channel": chan,
                        "message": message,
                        "hidden": cmd["hidden"],
                        "time_elapsed_ms": time_elapsed_ms,
                        "source": "bancho-service",
                    },
                ),
            )

        return {"response": command_response, "hidden": cmd["hidden"]}

    # No commands triggered
    return None
