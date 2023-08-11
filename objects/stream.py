from __future__ import annotations

from typing import TYPE_CHECKING

from objects import glob
from objects import osuToken


def make_key(stream_name: str) -> str:
    return f"bancho:streams:{stream_name}"


def getClients(stream_name: str) -> set[str]:
    """
    Get all clients in this stream

    :return: list of clients
    """
    raw_members: set[bytes] = glob.redis.smembers(make_key(stream_name))
    return {member.decode() for member in raw_members}


def getClientCount(stream_name: str) -> int:
    """
    Get the amount of clients in this stream

    :return: amount of clients
    """
    return glob.redis.scard(make_key(stream_name))


def addClient(stream_name: str, token_id: str) -> None:
    """
    Add a client to this stream if not already in

    :param client: client (osuToken) object
    :param token: client uuid string
    :return:
    """

    current_tokens = getClients(stream_name)

    if token_id not in current_tokens:
        # log.info("{} has joined stream {}.".format(token, self.name))
        glob.redis.sadd(make_key(stream_name), token_id)


def removeClient(
    stream_name: str,
    token_id: str,
) -> None:
    """
    Remove a client from this stream if in

    :param token_id: client uuid string
    :return:
    """
    current_tokens = getClients(stream_name)

    if token_id in current_tokens:
        glob.redis.srem(make_key(stream_name), token_id)


def broadcast(stream_name: str, data: bytes, but: list[str] = []) -> None:
    """
    Send some data to all (or some) clients connected to this stream

    :param data: data to send
    :param but: array of tokens to ignore. Default: None (send to everyone)
    :return:
    """
    current_tokens = getClients(stream_name)

    for i in current_tokens:
        if i in osuToken.get_token_ids():
            if i not in but:
                osuToken.enqueue(i, data)
        else:
            removeClient(stream_name, token_id=i)


def broadcast_limited(stream_name: str, data: bytes, users: list[str]) -> None:
    """
    Send some data to specific clients connected to this stream

    :param data: data to send
    :param users: array of tokens broadcast to.
    :return:
    """
    current_tokens = getClients(stream_name)

    for i in current_tokens:
        if i in osuToken.get_token_ids():
            if i in users:
                osuToken.enqueue(i, data)
        else:
            removeClient(stream_name, token_id=i)


def dispose(stream_name: str) -> None:
    """
    Tell every client in this stream to leave the stream

    :return:
    """
    current_tokens = getClients(stream_name)

    for i in current_tokens:
        if i in osuToken.get_token_ids():
            osuToken.leaveStream(i, stream_name)
