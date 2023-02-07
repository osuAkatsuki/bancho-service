from __future__ import annotations

from time import time
from typing import Optional

from common.log import logUtils as log
from common.constants import mods
from constants import serverPackets, matchScoringTypes, matchModModes, matchTeamTypes
from objects import slot
from objects import glob
from objects import match
from objects import streamList, channelList, tokenList, osuToken
from helpers import chatHelper as chat


def make_key() -> str:
    return "bancho:matches"


def createMatch(
    match_name: str,
    match_password: str,
    beatmap_id: int,
    beatmap_name: str,
    beatmap_md5: str,
    game_mode: int,
    host_user_id: int,
    is_tourney: bool = False,
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
    multiplayer_match = match.create_match(
        match_name=match_name,
        match_password=match_password,
        beatmap_id=beatmap_id,
        beatmap_name=beatmap_name,
        beatmap_md5=beatmap_md5,
        game_mode=game_mode,
        host_user_id=host_user_id,
        mods=mods.NOMOD,
        match_scoring_type=matchScoringTypes.SCORE,
        match_team_type=matchTeamTypes.HEAD_TO_HEAD,
        match_mod_mode=matchModModes.FREE_MOD,
        seed=0,  # TODO: what's the size, signedness, and time to set this?
        is_tourney=is_tourney,
        is_locked=False,
        is_starting=False,
        is_in_progress=False,
        creation_time=time(),
    )
    streamList.add(match.create_stream_name(multiplayer_match["match_id"]))
    streamList.add(match.create_playing_stream_name(multiplayer_match["match_id"]))
    channelList.addChannel(
        f"#multi_{multiplayer_match['match_id']}",
        description=f"Multiplayer lobby for match {multiplayer_match['match_name']}",
        public_read=True,
        public_write=False,
        moderated=False,
        instance=True,
    )

    return multiplayer_match["match_id"]


def disposeMatch(match_id: int) -> None:
    """
    Destroy match object with id = matchID

    :param matchID: ID of match to dispose
    :return:
    """
    # Make sure the match exists
    if match_id not in match.get_match_ids():
        return

    # Get match and disconnect all players
    multiplayer_match = match.get_match(match_id)
    assert multiplayer_match is not None

    slots = slot.get_slots(match_id)
    assert len(slots) == 16

    for _slot in slots:
        _token = tokenList.getTokenFromUserID(_slot["user_id"], ignoreIRC=True)
        if _token is not None:
            match.userLeft(
                match_id,
                _token["token_id"],
                # don't dispose the match twice when we remove all players
                disposeMatch=False,
            )

    # Delete chat channel
    channelList.removeChannel(f"#multi_{match_id}")

    stream_name = match.create_stream_name(match_id)
    playing_stream_name = match.create_playing_stream_name(match_id)

    # Send matchDisposed packet before disposing streams
    streamList.broadcast(stream_name, serverPackets.disposeMatch(match_id))

    # Dispose all streams
    streamList.dispose(stream_name)
    streamList.dispose(playing_stream_name)
    streamList.remove(stream_name)
    streamList.remove(playing_stream_name)

    # Send match dispose packet to everyone in lobby
    streamList.broadcast("lobby", serverPackets.disposeMatch(match_id))
    match.delete_match(match_id)


# deleting this code 2022-12-30 because
# https://twitter.com/elonmusk/status/1606624671100997634?cxt=HHwWhMDUhYmo8MssAAAA
# def cleanupLoop(self) -> None:
#     """
#     Start match cleanup loop.
#     Empty matches that have been created more than 60 seconds ago will get deleted.
#     Useful when people create useless lobbies with `!mp make`.
#     The check is done every 30 seconds.
#     This method starts an infinite loop, call it only once!
#     :return:
#     """
#     try:
#         log.debug("Checking empty matches")
#         t: int = int(time())
#         emptyMatches: list[int] = []
#         exceptions: list[Exception] = []

#         # Collect all empty matches
#         for _, m in self.matches.items():
#             if [x for x in m.slots if x.user]:
#                 continue
#             if t - m.createTime >= 120:
#                 log.debug(f"Match #{m.matchID} marked for cleanup")
#                 emptyMatches.append(m.matchID)

#         # Dispose all empty matches
#         for matchID in emptyMatches:
#             try:
#                 self.disposeMatch(matchID)
#             except Exception as e:
#                 exceptions.append(e)
#                 log.error(
#                     "Something wrong happened while disposing a timed out match.",
#                 )

#         # Re-raise exception if needed
#         if exceptions:
#             raise periodicLoopException(exceptions)
#     finally:
#         # Schedule a new check (endless loop)
#         Timer(30, self.cleanupLoop).start()


def matchExists(matchID: int) -> bool:
    return matchID in match.get_match_ids()


def getMatchByID(match_id: int) -> Optional[match.Match]:
    if matchExists(match_id):
        return match.get_match(match_id)


# this is the duplicate of channelList.getMatchFromChannel. I don't know where to put this function actually. Maybe it's better to be here.
def getMatchFromChannel(chan: str) -> Optional[match.Match]:
    return getMatchByID(channelList.getMatchIDFromChannel(chan))
