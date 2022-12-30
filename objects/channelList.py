from __future__ import annotations

from cmyui.logging import Ansi
from cmyui.logging import log

from typing import Optional
from typing import TypedDict

from constants import exceptions
from helpers import chatHelper as chat
import json
from objects import glob
from objects import stream,streamList
import logging

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

def loadChannels() -> None:
    """
    Load chat channels from db and add them to channels list
    :return:
    """
    # Get channels from DB
    channels = glob.db.fetchAll("SELECT * FROM bancho_channels")
    assert channels is not None

    # Add each channel if needed
    for chan in channels:
        current_channels = glob.redis.smembers("bancho:channels")
        if chan["name"] in current_channels:
            continue

        glob.redis.sadd("bancho:channels", chan["name"])
        glob.redis.set(make_key(chan['name']), json.dumps({
            "name": chan["name"],
            "description": chan["description"],
            "public_read": chan["public_read"] == 1,
            "public_write": chan["public_write"] == 1,
            "moderated": False,
            "instance": False ,# all db tables are not
        }))

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
            breakpoint()
        channels.append(channel)
    return channels

def addChannel(
    name: str,
    description: str,
    publicRead: bool,
    publicWrite: bool,
    instance: bool = False,
) -> None:
    """
    Add a channel to channels list
    :param name: channel name
    :param description: channel description
    :param publicRead: if True, this channel can be read by everyone. If False, it can be read only by mods/admins
    :param publicWrite: same as public read, but regards writing permissions
    :param temp: if True, this channel will be deleted when there's no one in this channel
    :param hidden: if True, thic channel won't be shown in channels list
    :return:
    """
    streamList.add(f"chat/{name}")
    glob.redis.set(
        make_key(name),
        json.dumps({
            "name": name,
            "description": description,
            "public_read": publicRead,
            "public_write": publicWrite,
            "moderated": False,
            "instance": instance,
        }),
    )
    # Make Foka join the channel
    fokaToken = glob.tokens.getTokenFromUserID(999)
    if fokaToken:
        try:
            fokaToken.joinChannel(name)
        except exceptions.userAlreadyInChannelException:
            logging.warning(f"{glob.BOT_NAME} has already joined channel {name}")
    log(f"Created channel {name}.")

def addInstanceChannel(name: str) -> None:
    """
    Add a temporary channel (like #spectator or #multiplayer), gets deleted when there's no one in the channel
    and it's hidden in channels list
    :param name: channel name
    :return:
    """
    current_channels = getChannelNames()
    if name in current_channels:
        logging.warning("Tried to create an instance channel that already exists!")
        return None

    streamList.add(f"chat/{name}")
    glob.redis.set(
        make_key(name),
        json.dumps({
            "name": name,
            "description": "Chat",
            "public_read": True,
            "public_write": True,
            "moderated": False,
            "instance": True,
        }),
    )

    # Make Foka join the channel
    fokaToken = glob.tokens.getTokenFromUserID(999)
    if fokaToken:
        try:
            fokaToken.joinChannel(name)
        except exceptions.userAlreadyInChannelException:
            logging.warning(f"{glob.BOT_NAME} has already joined channel {name}")
    log(f"Created temp channel {name}.")

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

    # streamList.broadcast(f"chat/{name}", serverPackets.channelKicked(name))
    for token in stream.getClients(f"chat/{name}"):
        if token in glob.tokens.tokens:
            chat.partChannel(
                channel_name=name,
                token=glob.tokens.tokens[token],
                kick=True,
            )
    streamList.dispose(f"chat/{name}")
    streamList.remove(f"chat/{name}")
    glob.redis.delete(make_key(name))
    log(f"Removed channel {name}.")

def updateChannel(
    name: str,
    description: Optional[str] = None,
    public_read: Optional[bool] = None,
    public_write: Optional[bool] = None,
    moderated: Optional[bool] = None,
    instance: Optional[bool] = None,
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
    if moderated is not None:
        channel["moderated"] = moderated
    if instance is not None:
        channel["instance"] = instance

    glob.redis.set(make_key(name), json.dumps(channel))
    log(f"Updated channel {name}.")

def getMatchIDFromChannel(channel_name: str) -> int:
    if not channel_name.lower().startswith("#multi_"):
        raise exceptions.wrongChannelException()

    parts = channel_name.lower().split("_")
    if len(parts) < 2 or not parts[1].isdigit():
        raise exceptions.wrongChannelException()

    matchID = int(parts[1])
    if matchID not in glob.matches.matches:
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
