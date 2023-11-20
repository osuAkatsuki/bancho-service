from __future__ import annotations

from objects import glob
from objects import osuToken
from objects import stream


def make_key() -> str:
    return f"bancho:streams"


async def getStreams() -> set[str]:
    """
    Returns a list of all streams

    :return:
    """
    raw_streams: set[bytes] = await glob.redis.smembers(make_key())
    return {stream.decode() for stream in raw_streams}


async def add(name: str) -> None:
    """
    Create a new stream list if it doesn't already exist

    :param name: stream name
    :return:
    """

    if not stream.has_member(make_key(), name):
        await glob.redis.sadd(make_key(), name)


async def remove(name: str) -> None:
    """
    Removes an existing stream and kick every user in it

    :param name: stream name
    :return:
    """
    if not stream.has_member(make_key(), name):
        current_clients = await stream.getClients(name)
        for i in current_clients:
            if i in await osuToken.get_token_ids():
                await osuToken.leaveStream(i, name)

        # self.streams.pop(name)
        previous_members = await stream.getClients(name)
        for token in previous_members:
            await stream.removeClient(name, token_id=token)
        await glob.redis.srem(make_key(), name)


async def join(name: str, token_id: str) -> None:
    """
    Add a client to a stream

    :param name: stream name
    :param client: client (osuToken) object
    :param token: client uuid string
    :return:
    """

    if stream.has_member(make_key(), name):
        await stream.addClient(name, token_id)


async def leave(
    name: str,
    token_id: str,
) -> None:
    """
    Remove a client from a stream

    :param name: stream name
    :param client: client (osuToken) object
    :param token: client uuid string
    :return:
    """

    if stream.has_member(make_key(), name):
        await stream.removeClient(name, token_id)


async def broadcast(name: str, data: bytes, but: list[str] = []) -> None:
    """
    Send some data to all clients in a stream

    :param name: stream name
    :param data: data to send
    :param but: array of tokens to ignore. Default: None (send to everyone)
    :return:
    """

    if stream.has_member(make_key(), name):
        await stream.broadcast(name, data, but)


async def broadcast_limited(name: str, data: bytes, users: list[str]) -> None:
    """
    Send some data to specific clients in a stream

    :param name: stream name
    :param data: data to send
    :param users: array of tokens to broadcast to
    :return:
    """

    if stream.has_member(make_key(), name):
        await stream.broadcast_limited(name, data, users)


async def dispose(name: str, *args, **kwargs) -> None:
    """
    Call `dispose` on `name`

    :param name: name of the stream
    :param args:
    :param kwargs:
    :return:
    """

    if stream.has_member(make_key(), name):
        await stream.dispose(name, *args, **kwargs)
