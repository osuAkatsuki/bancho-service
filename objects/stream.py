from __future__ import annotations

import logging

from objects import glob
from objects import osuToken


def make_key(stream_name: str) -> str:
    return f"bancho:streams:{stream_name}"


async def get_client_token_ids(stream_name: str) -> set[str]:
    """
    Get all clients in this stream

    :return: list of clients
    """
    raw_token_ids: set[bytes] = await glob.redis.smembers(make_key(stream_name))
    return {member.decode() for member in raw_token_ids}


async def get_client_count(stream_name: str) -> int:
    """
    Get the amount of clients in this stream

    :return: amount of clients
    """
    return await glob.redis.scard(make_key(stream_name))


async def add_client(stream_name: str, token_id: str) -> None:
    """
    Add a client to this stream if not already in

    :param client: client (osuToken) object
    :param token: client uuid string
    :return:
    """

    client_token_ids = await get_client_token_ids(stream_name)

    if token_id in client_token_ids:
        logging.warning(
            "Attempted to add client to stream which is already in",
            extra={"stream": stream_name, "token": token_id},
        )
        return

    await glob.redis.sadd(make_key(stream_name), token_id)


async def remove_client(
    stream_name: str,
    token_id: str,
) -> None:
    """
    Remove a client from this stream if in

    :param token_id: client uuid string
    :return:
    """
    client_token_ids = await get_client_token_ids(stream_name)

    if token_id not in client_token_ids:
        logging.warning(
            "Attempted to remove client from stream which is not in",
            extra={"stream": stream_name, "token": token_id},
        )
        return

    await glob.redis.srem(make_key(stream_name), token_id)


async def broadcast_data(stream_name: str, data: bytes, but: list[str] = []) -> None:
    """
    Send some data to all (or some) clients connected to this stream

    :param data: data to send
    :param but: array of tokens to ignore. Default: None (send to everyone)
    :return:
    """
    client_token_ids = await get_client_token_ids(stream_name)

    for token_id in client_token_ids:
        if token_id not in but:
            await osuToken.enqueue(token_id, data)


async def multicast_data(stream_name: str, data: bytes, users: list[str]) -> None:
    """
    Send some data to specific clients connected to this stream

    :param data: data to send
    :param users: array of tokens broadcast to.
    :return:
    """
    client_token_ids = await get_client_token_ids(stream_name)

    for token_id in client_token_ids:
        if token_id in users:
            await osuToken.enqueue(token_id, data)


async def dispose(stream_name: str) -> None:
    """
    Tell every client in this stream to leave the stream

    :return:
    """
    client_token_ids = await get_client_token_ids(stream_name)

    for token_id in client_token_ids:
        await osuToken.leaveStream(token_id, stream_name)
