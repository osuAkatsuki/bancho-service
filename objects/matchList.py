from __future__ import annotations

import asyncio
from time import time
from typing import MutableMapping
from typing import Optional

from common.log import logUtils as log
from constants import serverPackets
from constants.exceptions import periodicLoopException
from objects import glob
from objects import match


class matchList:
    __slots__ = ("matches", "lastID")

    def __init__(self) -> None:
        """Initialize a matchList object"""
        self.matches: MutableMapping[int, match.match] = {}
        self.lastID: int = 1

    def createMatch(
        self,
        matchName: str,
        matchPassword: str,
        beatmapID: int,
        beatmapName: str,
        beatmapMD5: str,
        gameMode: int,
        hostUserID: int,
        isTourney: bool = False,
    ) -> int:
        """
        Add a new match to matches list

        :param matchName: match name, string
        :param matchPassword: match md5 password. Leave empty for no password
        :param beatmapID: beatmap ID
        :param beatmapName: beatmap name, string
        :param beatmapMD5: beatmap md5 hash, string
        :param gameMode: game mode ID. See gameModes.py
        :param hostUserID: user id of who created the match
        :return: match ID
        """
        # Add a new match to matches list and create its stream
        matchID = self.lastID
        self.lastID += 1
        self.matches[matchID] = match.match(
            matchID,
            matchName,
            matchPassword,
            beatmapID,
            beatmapName,
            beatmapMD5,
            gameMode,
            hostUserID,
            isTourney,
        )
        return matchID

    def disposeMatch(self, matchID: int) -> None:
        """
        Destroy match object with id = matchID

        :param matchID: ID of match to dispose
        :return:
        """
        # Make sure the match exists
        if matchID not in self.matches:
            return

        # Get match and disconnect all players
        _match = self.matches[matchID]
        for slot in _match.slots:
            _token = glob.tokens.getTokenFromUserID(slot.userID, ignoreIRC=True)
            if _token is None:
                continue
            _match.userLeft(
                _token,
                disposeMatch=False,
            )  # don't dispose the match twice when we remove all players

        # Delete chat channel
        glob.channels.removeChannel(f"#multi_{_match.matchID}")

        # Send matchDisposed packet before disposing streams
        glob.streams.broadcast(
            _match.streamName,
            serverPackets.disposeMatch(_match.matchID),
        )

        # Dispose all streams
        glob.streams.dispose(_match.streamName)
        glob.streams.dispose(_match.playingStreamName)
        glob.streams.remove(_match.streamName)
        glob.streams.remove(_match.playingStreamName)

        # Send match dispose packet to everyone in lobby
        glob.streams.broadcast("lobby", serverPackets.disposeMatch(matchID))
        del self.matches[matchID]
        log.info(f"MPROOM{_match.matchID}: Room disposed manually")

    async def cleanupLoop(self) -> None:
        """
        Start match cleanup loop.
        Empty matches that have been created more than 60 seconds ago will get deleted.
        Useful when people create useless lobbies with `!mp make`.
        The check is done every 30 seconds.
        This method starts an infinite loop, call it only once!
        :return:
        """
        while True:
            log.debug("Checking empty matches")
            t: int = int(time())
            emptyMatches: list[int] = []

            # Collect all empty matches
            for _, m in self.matches.items():
                if [x for x in m.slots if x.user]:
                    continue
                if t - m.createTime >= 120:
                    log.debug(f"Match #{m.matchID} marked for cleanup")
                    emptyMatches.append(m.matchID)

            # Dispose all empty matches
            for matchID in emptyMatches:
                # TODO: handle & log exceptions in this call gracefully?
                self.disposeMatch(matchID)

            await asyncio.sleep(30)

    def matchExists(self, matchID: int) -> bool:
        return matchID in self.matches

    def getMatchByID(self, matchID: int) -> Optional[match.match]:
        log.debug(f"call: getMatchByID,id={matchID}")
        if self.matchExists(matchID):
            return self.matches[matchID]

    # this is the duplicate of channelList.getMatchFromChannel. I don't know where to put this function actually. Maybe it's better to be here.
    def getMatchFromChannel(self, chan: str) -> Optional[match.match]:
        log.debug(f"call: getMatchFromChannel,channel={chan}")
        return self.getMatchByID(glob.channels.getMatchIDFromChannel(chan))
