from __future__ import annotations

import json
import logging
from typing import Optional
from typing import TypedDict

from cmyui.logging import Ansi
from cmyui.logging import log

from constants import exceptions
from constants import serverPackets
from helpers import chatHelper as chat
from objects import glob
from objects import match
from objects import osuToken
from objects import stream
from objects import streamList
from objects import tokenList

# bancho:channels
# bancho:channels:{channel_name}


class Channel(TypedDict):
    name: str
    description: str
    public_read: bool
    public_write: bool
    moderated: bool
    instance: bool


def make_key(channel_name: str) -> str:
    # TODO: do we need a channel id? redis keys cannot have spaces.
    return f"bancho:channels:{channel_name}"


async def loadChannels() -> None:
    """
    Load chat channels from db and add them to channels list
    :return:
    """
    # Get channels from DB
    channels = await glob.db.fetchAll("SELECT * FROM bancho_channels")
    assert channels is not None

    # Add each channel if needed
    current_channels = glob.redis.smembers("bancho:channels")
    for chan in channels:
        if chan["name"] not in current_channels:
            addChannel(
                chan["name"],
                chan["description"],
                chan["public_read"] == 1,
                chan["public_write"] == 1,
                instance=False,
            )


def getChannelNames() -> set[str]:
    """
    Get all channels from channels list
    :return: list of channels
    """
    raw_channel_names: set[bytes] = glob.redis.smembers("bancho:channels")
    return {name.decode() for name in raw_channel_names}


def getChannel(channel_name: str) -> Optional[Channel]:
    """
    Get all channels from channels list
    :return: list of channels
    """
    raw_channel = glob.redis.get(f"bancho:channels:{channel_name}")
    if raw_channel is None:
        return None
    return json.loads(raw_channel)


def getChannels() -> list[Channel]:
    """
    Get all channels from channels list
    :return: list of channels
    """
    channels = []
    for channel_name in getChannelNames():
        channel = getChannel(channel_name)
        if channel is None:
            continue

        channels.append(channel)

    return channels


def addChannel(
    name: str,
    description: str,
    public_read: bool,
    public_write: bool,
    instance: bool = False,
    moderated: bool = False,
) -> None:
    """
    Add a channel to channels list
    :param name: channel name
    :param description: channel description
    :param public_read: if True, this channel can be read by everyone. If False, it can be read only by mods/admins
    :param public_write: same as public read, but regards writing permissions
    :param temp: if True, this channel will be deleted when there's no one in this channel
    :param hidden: if True, thic channel won't be shown in channels list
    :return:
    """
    channels = getChannelNames()
    if name in channels:
        return

    streamList.add(f"chat/{name}")
    glob.redis.sadd("bancho:channels", name)
    glob.redis.set(
        make_key(name),
        json.dumps(
            {
                "name": name,
                "description": description,
                "public_read": public_read,
                "public_write": public_write,
                "instance": instance,
                "moderated": moderated,
            },
        ),
    )
    # Make Foka join the channel
    fokaToken = tokenList.getTokenFromUserID(999)
    assert fokaToken is not None
    if fokaToken:
        try:
            osuToken.joinChannel(fokaToken["token_id"], name)
        except exceptions.userAlreadyInChannelException:
            logging.warning(f"{glob.BOT_NAME} has already joined channel {name}")
    log(f"Created channel {name}.")


def removeChannel(name: str) -> None:
    """
    Removes a channel from channels list
    :param name: channel name
    :return:
    """
    channels = getChannelNames()
    if name not in channels:
        log(f"{name} is not in channels list?", Ansi.LYELLOW)
        return

    streamList.broadcast(f"chat/{name}", serverPackets.channelKicked(name))
    for token_id in stream.getClients(f"chat/{name}"):
        token = osuToken.get_token(token_id)
        if token is not None:
            chat.partChannel(
                channel_name=name,
                token_id=token_id,
                kick=True,
            )
    streamList.dispose(f"chat/{name}")
    streamList.remove(f"chat/{name}")
    glob.redis.delete(make_key(name))
    glob.redis.srem("bancho:channels", name)
    log(f"Removed channel {name}.")


def updateChannel(
    name: str,
    description: Optional[str] = None,
    public_read: Optional[bool] = None,
    public_write: Optional[bool] = None,
    instance: Optional[bool] = None,
    moderated: Optional[bool] = None,
) -> None:
    """
    Updates a channel
    :param name: channel name
    :param description: channel description
    :param public_read: if True, this channel can be read by everyone. If False, it can be read only by mods/admins
    :param public_write: same as public read, but regards writing permissions
    :return:
    """
    channel = getChannel(name)
    if channel is None:
        raise exceptions.channelUnknownException()

    if description is not None:
        channel["description"] = description
    if public_read is not None:
        channel["public_read"] = public_read
    if public_write is not None:
        channel["public_write"] = public_write
    if instance is not None:
        channel["instance"] = instance
    if moderated is not None:
        channel["moderated"] = moderated

    glob.redis.set(make_key(name), json.dumps(channel))
    log(f"Updated channel {name}.")


def getMatchIDFromChannel(channel_name: str) -> int:
    if not channel_name.lower().startswith("#multi_"):
        raise exceptions.wrongChannelException()

    parts = channel_name.lower().split("_")
    if len(parts) < 2 or not parts[1].isdigit():
        raise exceptions.wrongChannelException()

    matchID = int(parts[1])
    if matchID not in match.get_match_ids():
        raise exceptions.matchNotFoundException()

    return matchID


def getSpectatorHostUserIDFromChannel(channel_name: str) -> int:
    if not channel_name.lower().startswith("#spect_"):
        raise exceptions.wrongChannelException()

    parts = channel_name.lower().split("_")
    if len(parts) < 2 or not parts[1].isdigit():
        raise exceptions.wrongChannelException()

    userID = int(parts[1])
    return userID
