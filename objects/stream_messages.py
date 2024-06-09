from __future__ import annotations

import logging
from typing import TypedDict

from objects import glob
from objects import streamList


def make_key(stream_name: str) -> str:
    return f"bancho:streams:{stream_name}:messages"


class StreamMessage(TypedDict):
    stream_key: str
    packet_data: bytes
    excluded_token_ids: str


async def broadcast_data(
    stream_name: str,
    data: bytes,
    *,
    excluded_token_ids: list[str] | None = None,
) -> None:
    """Send some data to all clients connected to this stream, with optional exclusions"""
    if excluded_token_ids is None:
        excluded_token_ids = []

    # TODO: potentially remove this check? it's ~55% of the function's wall time
    if not await streamList.stream_exists(stream_name):
        logging.warning(
            "Could not broadcast to stream which does not exist",
            extra={"stream_name": stream_name},
        )
        return

    stream_key = make_key(stream_name)
    fields: StreamMessage = {
        "stream_key": stream_key,
        "packet_data": data,
        "excluded_token_ids": ",".join(excluded_token_ids),
    }
    await glob.redis.xadd(stream_key, fields)


async def _get_token_stream_offsets(token_id: str) -> dict[str, str]:
    return {
        stream_key.decode(): stream_offset.decode()
        for stream_key, stream_offset in (
            await glob.redis.hgetall(f"bancho:tokens:{token_id}:stream_offsets")
        ).items()
    }


async def _set_token_stream_offsets(
    token_id: str,
    stream_offsets: dict[str, str],
) -> None:
    await glob.redis.hmset(
        f"bancho:tokens:{token_id}:stream_offsets",
        stream_offsets,  # type: ignore[arg-type]
    )


async def read_all_pending_data(token_id: str) -> bytes:
    """Read all data sent to these streams, excluding data sent by the client."""
    stream_offsets = await _get_token_stream_offsets(token_id)
    if not stream_offsets:
        logging.warning(
            "Token is connected to no streams",
            extra={"token_id": token_id},
        )
        return b""

    data = await glob.redis.xread(stream_offsets)

    pending_data = bytearray()
    new_stream_offsets: dict[str, str] = {}

    for stream_key, stream_data in data:
        message_id: bytes | None = None
        for message_id, fields in stream_data:
            excluded_token_ids = fields[b"excluded_token_ids"].decode().split(",")
            if token_id in excluded_token_ids:
                continue

            pending_data += fields[b"packet_data"]

        if message_id is not None:
            new_stream_offsets[stream_key.decode()] = message_id.decode()

    if new_stream_offsets:
        await _set_token_stream_offsets(token_id, new_stream_offsets)

    return pending_data


async def get_latest_message_id(stream_name: str) -> str:
    data = await glob.redis.xrevrange(make_key(stream_name), count=1)
    if not data:
        return "0-0"
    message_id: bytes = data[0][0]
    return message_id.decode()


async def trim_stream_messages(stream_name: str, min_id: str) -> int:
    num_messages: int = await glob.redis.xtrim(make_key(stream_name), minid=min_id)
    return num_messages
