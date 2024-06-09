from __future__ import annotations

import asyncio
import logging

from objects import glob
from objects import stream


def make_key() -> str:
    return "bancho:streams"


async def getStreams() -> set[str]:
    """Returns a list of all streams."""
    raw_streams: set[bytes] = await glob.redis.smembers(make_key())
    return {stream.decode() for stream in raw_streams}


async def stream_exists(name: str) -> bool:
    """Check if a stream exists."""
    return await glob.redis.sismember(make_key(), name) == 1


async def add(stream_name: str) -> None:
    """Create a new stream if it doesn't already exist."""
    if await stream_exists(stream_name):
        logging.warning(
            "Could not add stream which already exists",
            extra={"stream_name": stream_name},
        )
        return

    await glob.redis.sadd(make_key(), stream_name)


async def join(stream_name: str, token_id: str) -> None:
    """Add a client to a stream."""
    if not await stream_exists(stream_name):
        logging.warning(
            "Could not join stream which does not exist",
            extra={"stream_name": stream_name, "token_id": token_id},
        )
        return

    await stream.add_client(stream_name, token_id)


async def leave(stream_name: str, token_id: str) -> None:
    """Remove a client from a stream."""
    if not await stream_exists(stream_name):
        logging.warning(
            "Could not leave stream which does not exist",
            extra={"stream_name": stream_name, "token_id": token_id},
        )
        return

    await stream.remove_client(stream_name, token_id)


import time


async def xd(stream_name: str, et, st):
    client_count = await stream.get_client_count(stream_name)
    logging.info(
        "Broadcast timing",
        extra={
            "time_elapsed_ms": (et - st) * 1000,
            "client_count": client_count,
        },
    )


async def broadcast(
    stream_name: str,
    data: bytes,
    *,
    excluded_token_ids: list[str] | None = None,
) -> None:
    """Send some data to all clients in a stream."""
    if excluded_token_ids is None:
        excluded_token_ids = []

    st = time.time()
    if not await stream_exists(stream_name):
        logging.warning(
            "Could not broadcast to stream which does not exist",
            extra={"stream_name": stream_name},
        )
        return

    await stream.broadcast_data(
        stream_name=stream_name,
        data=data,
        excluded_token_ids=excluded_token_ids,
    )
    et = time.time()
    asyncio.create_task(xd(stream_name, et, st))


async def multicast(
    stream_name: str,
    data: bytes,
    *,
    recipient_token_ids: list[str],
) -> None:
    """Send some data to a set of specific clients in a stream."""
    if not await stream_exists(stream_name):
        logging.warning(
            "Could not multicast to stream which does not exist",
            extra={"stream_name": stream_name},
        )
        return

    await stream.multicast_data(
        stream_name,
        data,
        recipient_token_ids=recipient_token_ids,
    )


async def dispose(stream_name: str) -> None:
    """Removes an existing stream and kicks every user in it."""
    if not await stream_exists(stream_name):
        logging.warning(
            "Could not dispose stream which does not exist",
            extra={"stream_name": stream_name},
        )
        return

    await stream.dispose(stream_name)

    await glob.redis.srem(make_key(), stream_name)
