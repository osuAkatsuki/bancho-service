from __future__ import annotations

import re
from time import time
from typing import Optional
from typing import TypedDict

from common.constants import actions
from common.constants import privileges
from common.ripple import user_utils
from constants import CHATBOT_USER_ID
from constants import chatbotCommands
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


async def connect() -> None:
    async with redisLock(f"bancho:locks:aika"):
        token = await tokenList.getTokenFromUserID(CHATBOT_USER_ID)
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
        token = await tokenList.getTokenFromUserID(CHATBOT_USER_ID)
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
) -> Optional[ChatbotResponse]:
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
        user_id = await user_utils.get_id_from_username(fro)
        user_privileges = await user_utils.get_privileges(user_id)

        # Make sure the user has right permissions
        if cmd["privileges"] and not user_privileges & cmd["privileges"]:
            return None

        # Check argument number
        message_split = message.split(" ")
        if cmd["syntax"] and len(message_split) <= cmd["syntax"].count(" ") + 1:
            return {
                "response": f'Incorrect syntax: {cmd["trigger"]} {cmd["syntax"]}',
                "hidden": True,
            }

        async def handle_command(cmd, fro, chan, msg):
            try:
                resp = await cmd["callback"](fro, chan, msg)
            except Exception as e:
                return e

            return resp

        if cmd["callback"]:
            resp = await handle_command(cmd, fro, chan, message_split[1:])
            if isinstance(resp, Exception):
                raise resp
        else:
            resp = cmd["response"]

        if not resp:
            return None

        resp = [resp]
        if user_privileges & privileges.ADMIN_CAKER:
            resp.append(f"Elapsed: {(time() - start_time) * 1000:.3f}ms")

        return {"response": " | ".join(resp), "hidden": cmd["hidden"]}

    # No commands triggered
    return None
