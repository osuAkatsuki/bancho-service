from __future__ import annotations

from objects import glob
from objects import osuToken


def make_key(stream_name: str) -> str:
    return f"bancho:streams:{stream_name}"


async def get_token_ids_in_stream(stream_name: str) -> set[str]:
    """
    Get all clients in this stream

    :return: list of clients
    """
    raw_members: set[bytes] = await glob.redis.smembers(make_key(stream_name))
    return {member.decode() for member in raw_members}


async def getClientCount(stream_name: str) -> int:
    """
    Get the amount of clients in this stream

    :return: amount of clients
    """
    return await glob.redis.scard(make_key(stream_name))


async def addClient(stream_name: str, token_id: str) -> None:
    """
    Add a client to this stream if not already in

    :param client: client (osuToken) object
    :param token: client uuid string
    :return:
    """

    tokens_in_stream = await get_token_ids_in_stream(stream_name)

    if token_id not in tokens_in_stream:
        # log.info("{} has joined stream {}.".format(token, self.name))
        await glob.redis.sadd(make_key(stream_name), token_id)


async def removeClient(
    stream_name: str,
    token_id: str,
) -> None:
    """
    Remove a client from this stream if in

    :param token_id: client uuid string
    :return:
    """
    tokens_in_stream = await get_token_ids_in_stream(stream_name)

    if token_id in tokens_in_stream:
        await glob.redis.srem(make_key(stream_name), token_id)


async def broadcast(stream_name: str, data: bytes, but: list[str] = []) -> None:
    """
    Send some data to all (or some) clients connected to this stream

    :param data: data to send
    :param but: array of tokens to ignore. Default: None (send to everyone)
    :return:
    """
    tokens_in_stream = await get_token_ids_in_stream(stream_name)

    for token_id in tokens_in_stream:
        if token_id not in but:
            await osuToken.enqueue(token_id, data)


async def multicast(stream_name: str, data: bytes, target_token_ids: list[str]) -> None:
    """
    Send some data to specific clients connected to this stream

    :param data: data to send
    :param users: array of tokens broadcast to.
    :return:
    """
    tokens_in_stream = await get_token_ids_in_stream(stream_name)

    for token_id in tokens_in_stream:
        if token_id in target_token_ids:
            await osuToken.enqueue(token_id, data)


async def dispose(stream_name: str) -> None:
    """
    Tell every client in this stream to leave the stream

    :return:
    """
    tokens_in_stream = await get_token_ids_in_stream(stream_name)

    for token_id in tokens_in_stream:
        await osuToken.leaveStream(token_id, stream_name)
