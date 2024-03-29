from __future__ import annotations

from typing import Optional
from typing import TypedDict

import orjson

from common.log import logger
from constants import CHATBOT_USER_ID
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
    current_channels = await glob.redis.smembers("bancho:channels")
    for chan in channels:
        if chan["name"] not in current_channels:
            await addChannel(
                chan["name"],
                chan["description"],
                chan["public_read"] == 1,
                chan["public_write"] == 1,
                instance=False,
            )


async def getChannelNames() -> set[str]:
    """
    Get all channels from channels list
    :return: list of channels
    """
    raw_channel_names: set[bytes] = await glob.redis.smembers("bancho:channels")
    return {name.decode() for name in raw_channel_names}


async def getChannel(channel_name: str) -> Optional[Channel]:
    """
    Get all channels from channels list
    :return: list of channels
    """
    raw_channel = await glob.redis.get(f"bancho:channels:{channel_name}")
    if raw_channel is None:
        return None
    return orjson.loads(raw_channel)


async def getChannels() -> list[Channel]:
    """
    Get all channels from channels list
    :return: list of channels
    """
    channels = []
    for channel_name in await getChannelNames():
        channel = await getChannel(channel_name)
        if channel is None:
            continue

        channels.append(channel)

    return channels


async def addChannel(
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
    channels = await getChannelNames()
    if name in channels:
        return

    await streamList.add(f"chat/{name}")
    await glob.redis.sadd("bancho:channels", name)
    await glob.redis.set(
        make_key(name),
        orjson.dumps(
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
    # Make the chatbot join the channel
    chatbot_token = await tokenList.getTokenFromUserID(CHATBOT_USER_ID)
    if chatbot_token:
        try:
            await osuToken.joinChannel(chatbot_token["token_id"], name)
        except exceptions.userAlreadyInChannelException:
            logger.warning(
                "User already in public chat channel",
                extra={"username": glob.BOT_NAME, "channel_name": name},
            )

    logger.info("Created chat channel in redis", extra={"channel_name": name})


async def removeChannel(name: str) -> None:
    """
    Removes a channel from channels list
    :param name: channel name
    :return:
    """
    channels = await getChannelNames()
    if name not in channels:
        logger.warning(
            "Attempted to remove channel from redis that does not exist",
            extra={"channel_name": name},
        )
        return

    await streamList.broadcast(f"chat/{name}", serverPackets.channelKicked(name))
    for token_id in await stream.getClients(f"chat/{name}"):
        token = await osuToken.get_token(token_id)
        if token is not None:
            await chat.partChannel(
                channel_name=name,
                token_id=token_id,
                kick=True,
            )
    await streamList.dispose(f"chat/{name}")
    await streamList.remove(f"chat/{name}")
    await glob.redis.delete(make_key(name))
    await glob.redis.srem("bancho:channels", name)
    logger.info("Deleted channel from redis", extra={"channel_name": name})


async def updateChannel(
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
    channel = await getChannel(name)
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

    await glob.redis.set(make_key(name), orjson.dumps(channel))
    logger.info("Updated channel in redis", extra={"channel_name": name})


async def getMatchIDFromChannel(channel_name: str) -> int:
    if not channel_name.lower().startswith("#multi_"):
        raise exceptions.wrongChannelException()

    parts = channel_name.lower().split("_")
    if len(parts) < 2 or not parts[1].isdigit():
        raise exceptions.wrongChannelException()

    matchID = int(parts[1])
    if matchID not in await match.get_match_ids():
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
