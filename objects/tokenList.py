from __future__ import annotations

import threading
import time
from types import TracebackType
from typing import Literal
from typing import MutableMapping
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


class tokenList:
    __slots__ = ("tokens", "_lock")

    def __init__(self) -> None:
        self.tokens: MutableMapping[str, osuToken.token] = {}
        self._lock = threading.Lock()

    def __enter__(self) -> tokenList:
        self._lock.acquire()
        return self

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> bool:
        self._lock.release()
        return exc_value is not None

    def addToken(
        self,
        userID: int,
        ip: str = "",
        irc: bool = False,
        timeOffset: int = 0,
        tournament: bool = False,
    ) -> osuToken.token:
        """
        Add a token object to tokens list

        :param userID: user id associated to that token
        :param ip: ip address of the client
        :param irc: if True, set this token as IRC client
        :param timeOffset: the time offset from UTC for this user. Default: 0.
        :param tournament: if True, flag this client as a tournement client. Default: True.
        :return: token object
        """
        newToken = osuToken.token(
            userID,
            ip=ip,
            irc=irc,
            timeOffset=timeOffset,
            tournament=tournament,
        )
        self.tokens[newToken.token] = newToken
        glob.redis.incr("ripple:online_users")
        return newToken

    def deleteToken(self, token: str) -> None:
        """
        Delete a token from token list if it exists

        :param token: token string
        :return:
        """
        if token in self.tokens:
            if self.tokens[token].ip:
                userUtils.deleteBanchoSessions(
                    self.tokens[token].userID,
                    self.tokens[token].ip,
                )
            t = self.tokens.pop(token)
            del t
            glob.redis.decr("ripple:online_users")

    def getUserIDFromToken(self, token: str) -> Optional[int]:
        """
        Get user ID from a token

        :param token: token to find
        :return: None if not found, userID if found
        """
        if token in self.tokens:
            return self.tokens[token].userID

    @overload
    def getTokenFromUserID(
        self,
        userID: int,
        ignoreIRC: bool = ...,
        _all: Literal[False] = ...,
    ) -> Optional[osuToken.token]:
        ...

    @overload
    def getTokenFromUserID(
        self,
        userID: int,
        ignoreIRC: bool = ...,
        _all: Literal[True] = ...,
    ) -> list[osuToken.token]:
        ...

    def getTokenFromUserID(
        self,
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
        for value in self.tokens.values():
            if value.userID == userID:
                if ignoreIRC and value.irc:
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
        self,
        username: str,
        ignoreIRC: bool = ...,
        safe: bool = False,
        _all: Literal[False] = ...,
    ) -> Optional[osuToken.token]:
        ...

    @overload
    def getTokenFromUsername(
        self,
        username: str,
        ignoreIRC: bool = ...,
        safe: bool = False,
        _all: Literal[True] = ...,
    ) -> list[osuToken.token]:
        ...

    def getTokenFromUsername(
        self,
        username: str,
        ignoreIRC: bool = False,
        safe: bool = False,
        _all: bool = False,
    ):
        """
        Get an osuToken object from an username

        :param username: normal username or safe username
        :param ignoreIRC: if True, consider bancho clients only and skip IRC clients
        :param safe: 	if True, username is a safe username,
                        compare it with token's safe username rather than normal username
        :param _all: if True, return a list with all clients that match given username, otherwise return
                    only the first occurrence.
        :return: osuToken object or None
        """
        # lowercase
        who = username.lower() if not safe else username

        # Make sure the token exists
        ret = []
        for value in self.tokens.values():
            if (not safe and value.username.lower() == who) or (
                safe and value.safeUsername == who
            ):
                if ignoreIRC and value.irc:
                    continue
                if _all:
                    ret.append(value)
                else:
                    return value

        # Return full list or None if not found
        if _all:
            return ret

    def deleteOldTokens(self, userID: int) -> None:
        """
        Delete old userID's tokens if found

        :param userID: tokens associated to this user will be deleted
        :return:
        """
        # Delete older tokens
        delete = []
        for key, value in list(self.tokens.items()):
            if value.userID == userID:
                # Delete this token from the dictionary
                # self.tokens[key].kick("You have logged in from somewhere else. You can't connect to Bancho/IRC from more than one device at the same time.", "kicked, multiple clients")
                delete.append(self.tokens[key])

        for i in delete:
            logoutEvent.handle(i)

    def multipleEnqueue(self, packet: bytes, who: list[int], but: bool = False) -> None:
        """
        Enqueue a packet to multiple users

        :param packet: packet bytes to enqueue
        :param who: userIDs array
        :param but: if True, enqueue to everyone but users in `who` array
        :return:
        """
        for value in self.tokens.values():
            shouldEnqueue = False
            if value.userID in who and not but:
                shouldEnqueue = True
            elif value.userID not in who and but:
                shouldEnqueue = True

            if shouldEnqueue:
                value.enqueue(packet)

    def enqueueAll(self, packet: bytes) -> None:
        """
        Enqueue packet(s) to every connected user

        :param packet: packet bytes to enqueue
        :return:
        """
        for value in self.tokens.values():
            value.enqueue(packet)

    def usersTimeoutCheckLoop(self) -> None:
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

            for key, value in self.tokens.items():
                # Check timeout (fokabot is ignored)
                if (
                    value.pingTime < timeoutLimit
                    and value.userID != 999
                    and not value.irc
                    and not value.tournament
                ):
                    # That user has timed out, add to disconnected tokens
                    # We can't delete it while iterating or items() throws an error
                    timedOutTokens.append(key)

            # Delete timed out users from self.tokens
            # i is token string (dictionary key)
            for i in timedOutTokens:
                log.warning(f"{self.tokens[i].username} timed out!!")
                self.tokens[i].enqueue(
                    serverPackets.notification(
                        "Your connection to the server timed out.",
                    ),
                )
                try:
                    logoutEvent.handle(self.tokens[i], None)
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
            threading.Timer(100, self.usersTimeoutCheckLoop).start()

    def spamProtectionResetLoop(self) -> None:
        """
        Start spam protection reset loop.
        Called every 10 seconds.
        CALL THIS FUNCTION ONLY ONCE!

        :return:
        """

        try:
            # Reset spamRate for every token
            for value in self.tokens.values():
                value.spamRate = 0
        finally:
            # Schedule a new check (endless loop)
            threading.Timer(10, self.spamProtectionResetLoop).start()

    def deleteBanchoSessions(self) -> None:
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
        self,
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
            return self.getTokenFromUserID(userID) is not None
        elif username is not None:
            return self.getTokenFromUsername(username) is not None
        else:
            raise RuntimeError("You must provide either a username or a userID")
