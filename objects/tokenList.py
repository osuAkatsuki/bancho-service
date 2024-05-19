from __future__ import annotations

from typing import Literal
from typing import Optional
from typing import Union
from typing import overload

from common.log import logger
from common.ripple import user_utils
from events import logoutEvent
from objects import glob
from objects import osuToken


async def addToken(
    user_id: int,
    ip: str = "",
    utc_offset: int = 0,
    tournament: bool = False,
    block_non_friends_dm: bool = False,
    amplitude_device_id: Optional[str] = None,
) -> osuToken.Token:
    """
    Add a token object to tokens list

    :param userID: user id associated to that token
    :param ip: ip address of the client
    :param timeOffset: the time offset from UTC for this user. Default: 0.
    :param tournament: if True, flag this client as a tournement client. Default: True.
    :return: token object
    """
    res = await glob.db.fetch(
        "SELECT username, privileges, whitelist FROM users WHERE id = %s",
        [user_id],
    )
    assert res is not None

    original_token = await osuToken.create_token(
        user_id,
        res["username"],
        res["privileges"],
        res["whitelist"],
        ip,
        utc_offset,
        tournament,
        block_non_friends_dm,
        amplitude_device_id,
    )

    await osuToken.updateCachedStats(original_token["token_id"])

    await osuToken.joinStream(original_token["token_id"], "main")

    token = await osuToken.get_token(original_token["token_id"])
    assert token is not None

    await glob.redis.set(
        "ripple:online_users",
        await osuToken.get_online_players_count(),
    )
    return token


async def deleteToken(token_id: str) -> None:
    """
    Delete a token from token list if it exists

    :param token: token string
    :return:
    """

    token = await osuToken.get_token(token_id)
    if token is None:
        logger.warning(
            "Token not found while attempting to delete it",
            extra={"token_id": token_id},
        )
        return

    await osuToken.delete_token(token_id)
    await glob.redis.set(
        "ripple:online_users",
        await osuToken.get_online_players_count(),
    )


async def getUserIDFromToken(token_id: str) -> Optional[int]:
    """
    Get user ID from a token

    :param token: token to find
    :return: None if not found, userID if found
    """
    token = await osuToken.get_token(token_id)
    if token is None:
        return None

    return token["user_id"]


async def deleteOldTokens(userID: int) -> None:
    """
    Delete old userID's tokens if found

    :param userID: tokens associated to this user will be deleted
    :return:
    """
    # Delete older tokens
    delete: list[osuToken.Token] = []
    for token in await osuToken.get_tokens():
        if token["user_id"] == userID:
            delete.append(token)

    for i in delete:
        await logoutEvent.handle(i)


async def multipleEnqueue(packet: bytes, who: list[int], but: bool = False) -> None:
    """
    Enqueue a packet to multiple users

    :param packet: packet bytes to enqueue
    :param who: userIDs array
    :param but: if True, enqueue to everyone but users in `who` array
    :return:
    """
    for value in await osuToken.get_tokens():
        shouldEnqueue = False
        if value["user_id"] in who and not but:
            shouldEnqueue = True
        elif value["user_id"] not in who and but:
            shouldEnqueue = True

        if shouldEnqueue:
            await osuToken.enqueue(value["token_id"], packet)


async def enqueueAll(packet: bytes) -> None:
    """
    Enqueue packet(s) to every connected user

    :param packet: packet bytes to enqueue
    :return:
    """
    for token_id in await osuToken.get_token_ids():
        await osuToken.enqueue(token_id, packet)
