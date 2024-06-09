import logging
from typing import TypedDict

from objects import glob, streamList


def make_key(stream_name: str) -> str:
    return f"bancho:streams:{stream_name}:messages"


class StreamMessage(TypedDict):
    stream_name: str
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

    if not await streamList.stream_exists(stream_name):
        logging.warning(
            "Could not broadcast to stream which does not exist",
            extra={"stream_name": stream_name},
        )
        return

    fields: StreamMessage = {
        "stream_name": stream_name,
        "packet_data": data,
        "excluded_token_ids": ",".join(excluded_token_ids),
    }
    await glob.redis.xadd(make_key(stream_name), fields)


async def _get_token_stream_offsets(token_id: str) -> dict[str, str]:
    return {
        make_key(stream_name): stream_offset
        for stream_name, stream_offset in (
            await glob.redis.hgetall(f"bancho:tokens:{token_id}:stream_offsets")
        ).items()
    }


async def read_all_pending_data(token_id: str) -> bytes:
    """Read all data sent to these streams, excluding data sent by the client."""
    stream_offsets = await _get_token_stream_offsets(token_id)
    data = await glob.redis.xread(stream_offsets)

    pending_data = bytearray()
    new_stream_offsets: dict[str, str] = {}
    for stream_name, stream_data in data:
        message_id: bytes | None = None
        for message_id, fields in stream_data:
            excluded_token_ids = fields["excluded_token_ids"].decode().split(",")
            if token_id in excluded_token_ids:
                continue

            pending_data += fields["packet_data"]

        if message_id is not None:
            new_stream_offsets[stream_name.decode()] = message_id.decode()

    if new_stream_offsets:
        await glob.redis.hmset(
            f"bancho:{token_id}:stream_offsets",
            new_stream_offsets,  # type: ignore
        )

    return pending_data
