from __future__ import annotations

from objects import glob
from objects import osuToken
from objects import stream


def make_key() -> str:
    return f"bancho:streams"


async def stream_exists(name: str) -> bool:
    return await glob.redis.sismember(make_key(), name)


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

    current_streams = await getStreams()
    if name not in current_streams:
        await glob.redis.sadd(make_key(), name)


async def remove(name: str) -> None:
    """
    Removes an existing stream and kick every user in it

    :param name: stream name
    :return:
    """
    current_streams = await getStreams()

    if name in current_streams:
        current_clients = await stream.get_token_ids_in_stream(name)
        for token_id in current_clients:
            if token_id in await osuToken.get_token_ids():
                await osuToken.leaveStream(token_id, name)

        # self.streams.pop(name)
        previous_members = await stream.get_token_ids_in_stream(name)
        for token_id in previous_members:
            await stream.removeClient(name, token_id)
        await glob.redis.srem(make_key(), name)


async def join(name: str, token_id: str) -> None:
    """
    Add a client to a stream

    :param name: stream name
    :param client: client (osuToken) object
    :param token: client uuid string
    :return:
    """

    if stream_exists(name):
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

    if stream_exists(name):
        await stream.removeClient(name, token_id)


async def broadcast(name: str, data: bytes, but: list[str] = []) -> None:
    """
    Send some data to all clients in a stream

    :param name: stream name
    :param data: data to send
    :param but: array of tokens to ignore. Default: None (send to everyone)
    :return:
    """

    if stream_exists(name):
        await stream.broadcast(name, data, but)


async def multicast(name: str, data: bytes, target_token_ids: list[str]) -> None:
    """
    Send some data to specific clients in a stream

    :param name: stream name
    :param data: data to send
    :param users: array of tokens to broadcast to
    :return:
    """

    if stream_exists(name):
        await stream.multicast(name, data, target_token_ids)


async def dispose(name: str) -> None:
    """
    Call `dispose` on `name`

    :param name: name of the stream
    :return:
    """

    if stream_exists(name):
        await stream.dispose(name)
