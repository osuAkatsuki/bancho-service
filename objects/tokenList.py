from __future__ import annotations

import threading
import time
from typing import Literal
from typing import Optional
from typing import overload

import redis

from common.log import logUtils as log
from common.ripple import userUtils
from constants import serverPackets
from constants.exceptions import periodicLoopException
from events import logoutEvent
from objects import glob
from objects import osuToken


# def __init__(self) -> None:
#     self.tokens: MutableMapping[str, osuToken.token] = {}
#     self._lock = threading.Lock()


def addToken(
    user_id: int,
    ip: str = "",
    irc: bool = False,
    utc_offset: int = 0,
    tournament: bool = False,
    block_non_friends_dm: bool = False,
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
    res = glob.db.fetch(
        "SELECT username, privileges, whitelist FROM users WHERE id = %s", [user_id]
    )
    assert res is not None

    token = osuToken.create_token(
        user_id,
        res["username"],
        res["privileges"],
        res["whitelist"],
        ip,
        utc_offset,
        irc,
        tournament,
        block_non_friends_dm,
    )

    osuToken.updateCachedStats(token["token_id"])
    if ip != "":
        userUtils.saveBanchoSession(token["user_id"], ip)

    osuToken.joinStream(token["token_id"], "main")

    token = osuToken.get_token(token["token_id"])
    assert token is not None

    glob.redis.incr("ripple:online_users")
    return token


def deleteToken(token_id: str) -> None:
    """
    Delete a token from token list if it exists

    :param token: token string
    :return:
    """

    token = osuToken.get_token(token_id)
    if token is None:
        return

    if token["ip"]:
        userUtils.deleteBanchoSessions(token["user_id"], token["ip"])

    osuToken.delete_token(token_id)
    glob.redis.decr("ripple:online_users")


def getUserIDFromToken(token_id: str) -> Optional[int]:
    """
    Get user ID from a token

    :param token: token to find
    :return: None if not found, userID if found
    """
    token = osuToken.get_token(token_id)
    if token is None:
        return

    return token["user_id"]


@overload
def getTokenFromUserID(
    userID: int,
    ignoreIRC: bool = ...,
    _all: Literal[False] = False,
) -> Optional[osuToken.Token]:
    ...


@overload
def getTokenFromUserID(
    userID: int,
    ignoreIRC: bool = ...,
    _all: Literal[True] = ...,
) -> list[osuToken.Token]:
    ...


def getTokenFromUserID(
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
    for value in osuToken.get_tokens():
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
def getTokenFromUsername(
    username: str,
    ignoreIRC: bool = ...,
    _all: Literal[False] = ...,
) -> Optional[osuToken.Token]:
    ...


@overload
def getTokenFromUsername(
    username: str,
    ignoreIRC: bool = ...,
    _all: Literal[True] = ...,
) -> list[osuToken.Token]:
    ...


def getTokenFromUsername(
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

    # Make sure the token exists
    ret = []
    for value in osuToken.get_tokens():
        if value["username"].lower().replace(" ", "_") == username.lower().replace(
            " ", "_"
        ):
            if ignoreIRC and value["irc"]:
                continue
            if _all:
                ret.append(value)
            else:
                return value

    # Return full list or None if not found
    if _all:
        return ret


def deleteOldTokens(userID: int) -> None:
    """
    Delete old userID's tokens if found

    :param userID: tokens associated to this user will be deleted
    :return:
    """
    # Delete older tokens
    delete = []
    for token in osuToken.get_tokens():
        if token["user_id"] == userID:
            delete.append(token["token_id"])

    for i in delete:
        logoutEvent.handle(i)


def multipleEnqueue(packet: bytes, who: list[int], but: bool = False) -> None:
    """
    Enqueue a packet to multiple users

    :param packet: packet bytes to enqueue
    :param who: userIDs array
    :param but: if True, enqueue to everyone but users in `who` array
    :return:
    """
    for value in osuToken.get_tokens():
        shouldEnqueue = False
        if value["user_id"] in who and not but:
            shouldEnqueue = True
        elif value["user_id"] not in who and but:
            shouldEnqueue = True

        if shouldEnqueue:
            osuToken.enqueue(value["token_id"], packet)


def enqueueAll(packet: bytes) -> None:
    """
    Enqueue packet(s) to every connected user

    :param packet: packet bytes to enqueue
    :return:
    """
    for token_id in osuToken.get_token_ids():
        osuToken.enqueue(token_id, packet)


def usersTimeoutCheckLoop() -> None:
    """
    Start timed out users disconnect loop.
    This function will be called every `checkTime` seconds and so on, forever.
    CALL THIS FUNCTION ONLY ONCE!
    :return:
    """
    try:
        log.debug("Checking timed out clients")
        exceptions = []
        timedOutTokens = []  # timed out users
        timeoutLimit = int(time.time()) - 300  # (determined by osu)

        for token in osuToken.get_tokens():
            # Check timeout (fokabot is ignored)
            if (
                token["ping_time"] < timeoutLimit
                and token["user_id"] != 999
                and not token["irc"]
                and not token["tournament"]
            ):
                # That user has timed out, add to disconnected tokens
                # We can't delete it while iterating or items() throws an error
                timedOutTokens.append(token)

        # Delete timed out users from self.tokens
        # i is token string (dictionary key)
        for i in timedOutTokens:
            log.warning(f"{i['username']} timed out!!")
            osuToken.enqueue(
                i["token_id"],
                serverPackets.notification(
                    "Your connection to the server timed out.",
                ),
            )
            try:
                logoutEvent.handle(i["token_id"], None)
            except Exception as e:
                exceptions.append(e)
                log.error(
                    "Something wrong happened while disconnecting a timed out client.",
                )
        del timedOutTokens

        # Re-raise exceptions if needed
        if exceptions:
            raise periodicLoopException(exceptions)
    finally:
        # Schedule a new check (endless loop)
        threading.Timer(100, usersTimeoutCheckLoop).start()


def spamProtectionResetLoop() -> None:
    """
    Start spam protection reset loop.
    Called every 10 seconds.
    CALL THIS FUNCTION ONLY ONCE!

    :return:
    """

    try:
        # Reset spamRate for every token
        for token_id in osuToken.get_token_ids():
            osuToken.update_token(
                token_id,
                spam_rate=0,
            )
    finally:
        # Schedule a new check (endless loop)
        threading.Timer(10, spamProtectionResetLoop).start()


def deleteBanchoSessions() -> None:
    """
    Remove all `peppy:sessions:*` redis keys.
    Call at bancho startup to delete old cached sessions

    :return:
    """
    try:
        # TODO: Make function or some redis meme
        glob.redis.eval(
            "return redis.call('del', unpack(redis.call('keys', ARGV[1])))",
            0,
            "peppy:sessions:*",
        )
    except redis.RedisError:
        pass


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
