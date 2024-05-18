from __future__ import annotations

import logging

from objects import glob
from objects import osuToken


def make_key(stream_name: str) -> str:
    return f"bancho:streams:{stream_name}"


async def get_client_token_ids(stream_name: str) -> set[str]:
    """Get all clients in this stream."""
    raw_token_ids: set[bytes] = await glob.redis.smembers(make_key(stream_name))
    return {member.decode() for member in raw_token_ids}


async def get_client_count(stream_name: str) -> int:
    """Get the amount of clients in this stream."""
    return await glob.redis.scard(make_key(stream_name))


async def add_client(stream_name: str, token_id: str) -> None:
    """Add a client to this stream if they are not a member."""
    client_token_ids = await get_client_token_ids(stream_name)

    if token_id in client_token_ids:
        logging.warning(
            "Attempted to add client to stream which is already in",
            extra={"stream_name": stream_name, "token_id": token_id},
        )
        return

    await glob.redis.sadd(make_key(stream_name), token_id)


async def remove_client(
    stream_name: str,
    token_id: str,
) -> None:
    """Remove a client from this stream if they are a member."""
    client_token_ids = await get_client_token_ids(stream_name)

    if token_id not in client_token_ids:
        logging.warning(
            "Attempted to remove client from stream which is not in",
            extra={"stream_name": stream_name, "token_id": token_id},
        )
        return

    await glob.redis.srem(make_key(stream_name), token_id)


async def broadcast_data(
    stream_name: str,
    data: bytes,
    *,
    excluded_token_ids: list[str] | None = None,
) -> None:
    """Send some data to all clients connected to this stream, with optional exclusions"""
    if excluded_token_ids is None:
        excluded_token_ids = []

    client_token_ids = await get_client_token_ids(stream_name)

    for token_id in client_token_ids:
        if token_id not in excluded_token_ids:
            await osuToken.enqueue(token_id, data)


async def multicast_data(
    stream_name: str,
    data: bytes,
    *,
    recipient_token_ids: list[str],
) -> None:
    """Send some data to specific clients connected to this stream."""
    client_token_ids = await get_client_token_ids(stream_name)

    for token_id in client_token_ids:
        if token_id in recipient_token_ids:
            await osuToken.enqueue(token_id, data)


async def dispose(stream_name: str) -> None:
    """Tell every client in this stream to leave the stream."""
    client_token_ids = await get_client_token_ids(stream_name)

    for token_id in client_token_ids:
        await osuToken.leaveStream(token_id, stream_name)
