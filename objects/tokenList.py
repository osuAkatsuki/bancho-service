from __future__ import annotations

import logging
from typing import Literal
from typing import Optional
from typing import overload

from common.ripple import userUtils
from events import logoutEvent
from objects import glob
from objects import osuToken


async def addToken(
    user_id: int,
    ip: str = "",
    irc: bool = False,
    utc_offset: int = 0,
    tournament: bool = False,
    block_non_friends_dm: bool = False,
    amplitude_device_id: Optional[str] = None,
) -> osuToken.Token:
    """
    Add a token object to tokens list

    :param userID: user id associated to that token
    :param ip: ip address of the client
    :param irc: if True, set this token as IRC client
    :param timeOffset: the time offset from UTC for this user. Default: 0.
    :param tournament: if True, flag this client as a tournement client. Default: True.
    :return: token object
    """
    res = await glob.db.fetch(
        "SELECT username, privileges, whitelist FROM users WHERE id = %s",
        [user_id],
    )
    assert res is not None

    token = await osuToken.create_token(
        user_id,
        res["username"],
        res["privileges"],
        res["whitelist"],
        ip,
        utc_offset,
        irc,
        tournament,
        block_non_friends_dm,
        amplitude_device_id,
    )

    await osuToken.updateCachedStats(token["token_id"])
    if ip != "":
        await userUtils.saveBanchoSessionIpLookup(token["user_id"], ip)

    await osuToken.joinStream(token["token_id"], "main")

    token = await osuToken.get_token(token["token_id"])
    assert token is not None

    await glob.redis.incr("ripple:online_users")
    return token


async def deleteToken(token_id: str) -> None:
    """
    Delete a token from token list if it exists

    :param token: token string
    :return:
    """

    token = await osuToken.get_token(token_id)
    if token is None:
        logging.warning(
            "Token not found while attempting to delete it",
            extra={"token_id": token_id},
        )
        return

    if token["ip"]:
        await userUtils.deleteBanchoSessionIpLookup(token["user_id"], token["ip"])

    await osuToken.delete_token(token_id)
    await glob.redis.decr("ripple:online_users")


async def getUserIDFromToken(token_id: str) -> Optional[int]:
    """
    Get user ID from a token

    :param token: token to find
    :return: None if not found, userID if found
    """
    token = await osuToken.get_token(token_id)
    if token is None:
        return

    return token["user_id"]


@overload
async def getTokenFromUserID(
    userID: int,
    ignoreIRC: bool = ...,
    _all: Literal[False] = False,
) -> Optional[osuToken.Token]:
    ...


@overload
async def getTokenFromUserID(
    userID: int,
    ignoreIRC: bool = ...,
    _all: Literal[True] = ...,
) -> list[osuToken.Token]:
    ...


async def getTokenFromUserID(
    userID: int,
    ignoreIRC: bool = False,
    _all: bool = False,
):
    """
    Get token from a user ID

    :param userID: user ID to find
    :param ignoreIRC: if True, consider bancho clients only and skip IRC clients
    :param _all: if True, return a list with all clients that match given username, otherwise return
                only the first occurrence.
    :return: False if not found, token object if found
    """
    # Make sure the token exists
    ret = []
    for value in await osuToken.get_tokens():
        if value["user_id"] == userID:
            if ignoreIRC and value["irc"]:
                continue
            if _all:
                ret.append(value)
            else:
                return value

    # Return full list or None if not found
    if _all:
        return ret


@overload
async def getTokenFromUsername(
    username: str,
    ignoreIRC: bool = ...,
    _all: Literal[False] = ...,
) -> Optional[osuToken.Token]:
    ...


@overload
async def getTokenFromUsername(
    username: str,
    ignoreIRC: bool = ...,
    _all: Literal[True] = ...,
) -> list[osuToken.Token]:
    ...


async def getTokenFromUsername(
    username: str,
    ignoreIRC: bool = False,
    _all: bool = False,
):
    """
    Get an osuToken object from an username

    :param username: normal username or safe username
    :param ignoreIRC: if True, consider bancho clients only and skip IRC clients
    :param _all: if True, return a list with all clients that match given username, otherwise return
                only the first occurrence.
    :return: osuToken object or None
    """
    username = userUtils.safeUsername(username)

    # Make sure the token exists
    ret = []
    for value in await osuToken.get_tokens():
        if userUtils.safeUsername(value["username"]) == username:
            if ignoreIRC and value["irc"]:
                continue
            if _all:
                ret.append(value)
            else:
                return value

    # Return full list or None if not found
    if _all:
        return ret


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


def tokenExists(
    username: Optional[str] = None,
    userID: Optional[int] = None,
) -> bool:
    """
    Check if a token exists
    Use username or userid, not both at the same time.

    :param username: Optional.
    :param userID: Optional.
    :return: True if it exists, otherwise False
    """
    if userID is not None:
        return getTokenFromUserID(userID) is not None
    elif username is not None:
        return getTokenFromUsername(username) is not None
    else:
        raise RuntimeError("You must provide either a username or a userID")
