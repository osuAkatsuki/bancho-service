from __future__ import annotations

from typing import TYPE_CHECKING

from objects import glob
from objects import stream
from objects import osuToken

if TYPE_CHECKING:
    from typing import Optional

def make_key() -> str:
    return f"bancho:streams"


def getStreams() -> set[str]:
    """
    Returns a list of all streams

    :return:
    """
    raw_streams: set[bytes] = glob.redis.smembers(make_key())
    return {stream.decode() for stream in raw_streams}

def add(name: str) -> None:
    """
    Create a new stream list if it doesn't already exist

    :param name: stream name
    :return:
    """

    current_streams = getStreams()
    if name not in current_streams:
        glob.redis.sadd(make_key(), name)

def remove(name: str) -> None:
    """
    Removes an existing stream and kick every user in it

    :param name: stream name
    :return:
    """
    current_streams = getStreams()

    if name in current_streams:
        current_clients = stream.getClients(name)
        for i in current_clients:
            if i in osuToken.get_token_ids():
                osuToken.leaveStream(i, name)

        #self.streams.pop(name)
        previous_members = stream.getClients(name)
        for token in previous_members:
            stream.removeClient(name, token_id=token)
        glob.redis.srem(make_key(), name)


def join(name: str, token_id: str) -> None:
    """
    Add a client to a stream

    :param name: stream name
    :param client: client (osuToken) object
    :param token: client uuid string
    :return:
    """

    streams = getStreams()
    if name in streams:
        stream.addClient(name, token_id)

def leave(
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

    streams = getStreams()
    if name in streams:
        stream.removeClient(name, token_id)

def broadcast(name: str, data: bytes, but: list[str] = []) -> None:
    """
    Send some data to all clients in a stream

    :param name: stream name
    :param data: data to send
    :param but: array of tokens to ignore. Default: None (send to everyone)
    :return:
    """

    streams = getStreams()
    if name in streams:
        stream.broadcast(name, data, but)

def broadcast_limited(name: str, data: bytes, users: list[str]) -> None:
    """
    Send some data to specific clients in a stream

    :param name: stream name
    :param data: data to send
    :param users: array of tokens to broadcast to
    :return:
    """

    streams = getStreams()
    if name in streams:
        stream.broadcast_limited(name, data, users)

def dispose(name: str, *args, **kwargs) -> None:
    """
    Call `dispose` on `name`

    :param name: name of the stream
    :param args:
    :param kwargs:
    :return:
    """

    streams = getStreams()
    if name in streams:
        stream.dispose(name, *args, **kwargs)
