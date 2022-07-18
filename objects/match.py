import json
import time
from copy import deepcopy
from threading import Lock
from types import TracebackType
from typing import Optional, Type

from common.log import logUtils as log
from constants import (dataTypes, matchModModes, matchScoringTypes, matchTeams,
                       matchTeamTypes, serverPackets, slotStatuses)
from helpers import chatHelper as chat
from objects import glob
from objects.osuToken import token


class slot:
    __slots__ = (
        'status', 'team', 'userID', 'user', 'mods', 'loaded',
        'skip', 'complete', 'score', 'failed', 'passed'
    )
    def __init__(self) -> None:
        self.status = slotStatuses.FREE
        self.team = matchTeams.NO_TEAM
        self.userID = -1
        self.user: Optional[str] = None # string of osutoken
        self.mods = 0
        self.loaded = False
        self.skip = False
        self.complete = False
        self.score = 0
        self.failed = False
        self.passed = True

class match:
    __slots__ = (
        'matchID', 'streamName', 'playingStreamName',
        'inProgress', 'mods', 'matchName', 'matchPassword',
        'beatmapID', 'beatmapName', 'beatmapMD5',
        'hostUserID', 'gameMode', 'matchScoringType',
        'matchTeamType', 'matchModMode', 'seed',
        'matchDataCache', 'isTourney', 'isLocked',
        'isStarting', '_lock', 'createTime',
        'bloodcatAlert', 'slots', 'refers'
    )
    def __init__(
        self, matchID: int, matchName: str, matchPassword: str,
        beatmapID: int, beatmapName: str, beatmapMD5: str,
        gameMode: int, hostUserID: int, isTourney: bool = False
    ) -> None:
        """
        Create a new match object

        :param matchID: match progressive identifier
        :param matchName: match name, string
        :param matchPassword: match md5 password. Leave empty for no password
        :param beatmapID: beatmap ID
        :param beatmapName: beatmap name, string
        :param beatmapMD5: beatmap md5 hash, string
        :param gameMode: game mode ID. See gameModes.py
        :param hostUserID: user id of the host
        """
        self.matchID = matchID
        self.streamName = f"multi/{self.matchID}"
        self.playingStreamName = f"{self.streamName}/playing"
        self.inProgress = False
        self.mods = 0
        self.matchName = matchName
        self.matchPassword = matchPassword
        self.beatmapID = beatmapID
        self.beatmapName = beatmapName
        self.beatmapMD5 = beatmapMD5
        self.hostUserID = hostUserID
        self.gameMode = gameMode
        self.matchScoringType = matchScoringTypes.SCORE	 # default values
        self.matchTeamType = matchTeamTypes.HEAD_TO_HEAD # default value
        self.matchModMode = matchModModes.NORMAL		 # default value
        self.seed = 0
        self.matchDataCache = b''
        self.isTourney = isTourney
        self.isLocked = False 	# if True, users can't change slots/teams. Used in tourney matches
        self.isStarting = False
        self._lock = Lock()
        self.createTime = int(time.time())
        self.bloodcatAlert = False

        # Create all slots and reset them
        self.slots = [slot() for _ in range(16)]

        # Create streams
        glob.streams.add(self.streamName)
        glob.streams.add(self.playingStreamName)

        # Create #multiplayer channel
        glob.channels.addHiddenChannel(f"#multi_{self.matchID}")

        # Create referrs array that couls use !mp command from fokabot.
        self.refers = {self.hostUserID}

    def add_referee(self, userID: int) -> None:
        self.refers.add(userID)

    def remove_referee(self, userID: int) -> None:
        self.refers.discard(userID)

    def is_referee(self, userID: int) -> bool:
        return userID in self.refers

    def getMatchData(self, censored: bool = False) -> tuple[tuple[object, int]]:
        """
        Return binary match data structure for packetHelper

        :return:
        """
        # General match info
        # TODO: Test without safe copy, the error might have been caused by outdated python bytecode cache
        # safeMatch = deepcopy(self)
        struct = [
            (self.matchID, dataTypes.UINT16),
            (int(self.inProgress), dataTypes.BYTE),
            (0, dataTypes.BYTE),
            (self.mods, dataTypes.UINT32),
            (self.matchName, dataTypes.STRING)
        ]
        if censored and self.matchPassword:
            struct.append(("redacted", dataTypes.STRING))
        else:
            struct.append((self.matchPassword, dataTypes.STRING))

        struct.extend([
            (self.beatmapName, dataTypes.STRING),
            (self.beatmapID, dataTypes.UINT32),
            (self.beatmapMD5, dataTypes.STRING)
        ])

        struct.extend([(slot.status, dataTypes.BYTE) for slot in self.slots])
        struct.extend([(slot.team, dataTypes.BYTE) for slot in self.slots])

        struct.extend([
            (glob.tokens.tokens[slot.user].userID, dataTypes.UINT32)
            for slot in self.slots if (
                slot.user and
                slot.user in glob.tokens.tokens
            )
        ])

        # Other match data
        struct.extend([
            (self.hostUserID, dataTypes.SINT32),
            (self.gameMode, dataTypes.BYTE),
            (self.matchScoringType, dataTypes.BYTE),
            (self.matchTeamType, dataTypes.BYTE),
            (self.matchModMode, dataTypes.BYTE),
        ])

        # Slot mods if free mod is enabled
        if self.matchModMode == matchModModes.FREE_MOD:
            struct.extend([(slot.mods, dataTypes.UINT32) for slot in self.slots])

        # Seed idk
        # TODO: Implement this, it should be used for mania "random" mod
        struct.append((self.seed, dataTypes.UINT32))

        return tuple(struct)

    def setHost(self, newHostID: int) -> bool:
        """
        Set room host to newHost and send him host packet

        :param newHost: new host userID
        :return:
        """

        old_host = glob.tokens.getTokenFromUserID(self.hostUserID)
        assert old_host is not None

        if not old_host.staff:
            self.remove_referee(self.hostUserID)

        self.add_referee(newHostID)

        slotID = self.getUserSlotID(newHostID)
        if slotID is None:
            return False

        slot_token = self.slots[slotID].user
        if slot_token is None or slot_token not in glob.tokens.tokens:
            return False

        self.hostUserID = newHostID

        user_token = glob.tokens.tokens[slot_token]
        user_token.enqueue(serverPackets.matchTransferHost)
        self.sendUpdates()
        return True

    def removeHost(self) -> None:
        """
        Removes the host (for tourney matches)
        :return:
        """

        self.remove_referee(self.hostUserID)
        self.hostUserID = -1
        self.sendUpdates()

    def setSlot(
        self, slotID: int, status: Optional[int] = None,
        team: Optional[int] = None, user: Optional[str] = "",
        mods: Optional[int] = None, loaded: Optional[bool] = None,
        skip: Optional[bool] = None, complete: Optional[bool] = None,
        userID: Optional[int] = None
    ) -> None:
        slot = self.slots[slotID]

        if status is not None:
            slot.status = status

        if team is not None:
            slot.team = team

        if user != "":
            slot.user = user # don't `is not None`, u will regret it due to ripple programming antics

        if userID is not None:
            slot.userID = userID

        if mods is not None:
            slot.mods = mods

        if loaded is not None:
            slot.loaded = loaded

        if skip is not None:
            slot.skip = skip

        if complete is not None:
            slot.complete = complete


    def setSlotMods(self, slotID: int, mods: int) -> None:
        """
        Set slotID mods. Same as calling setSlot and then sendUpdate

        :param slotID: slot number
        :param mods: new mods
        :return:
        """
        # Set new slot data and send update
        self.setSlot(slotID, mods=mods)
        self.sendUpdates()

    def toggleSlotReady(self, slotID: int) -> None:
        """
        Switch slotID ready/not ready status
        Same as calling setSlot and then sendUpdate

        :param slotID: slot number
        :return:
        """
        slot = self.slots[slotID]

        # Update ready status and setnd update
        if not slot.user or self.isStarting:
            return

        oldStatus = slot.status
        if oldStatus == slotStatuses.READY:
            newStatus = slotStatuses.NOT_READY
        else:
            newStatus = slotStatuses.READY

        self.setSlot(slotID, newStatus)
        self.sendUpdates()

    def toggleSlotLocked(self, slotID: int) -> None:
        """
        Lock a slot
        Same as calling setSlot and then sendUpdate

        :param slotID: slot number
        :return:
        """

        slot = self.slots[slotID]

        # Check if slot is already locked
        if slot.status == slotStatuses.LOCKED:
            newStatus = slotStatuses.FREE
        else:
            newStatus = slotStatuses.LOCKED

        # Send updated settings to kicked user, so he returns to lobby
        if (
            slot.user and
            slot.user in glob.tokens.tokens
        ):
            glob.tokens.tokens[slot.user].enqueue(serverPackets.updateMatch(self.matchID))

        # Set new slot status
        self.setSlot(
            slotID = slotID,
            status = newStatus,
            team = 0,
            user = None,
            mods = 0,
            userID = -1
        )

        # Send updates to everyone else
        self.sendUpdates()

    def playerLoaded(self, userID: int) -> None:
        """
        Set a player loaded status to True

        :param userID: ID of user
        :return:
        """
        slotID = self.getUserSlotID(userID)
        if slotID is None:
            return

        # Set loaded to True
        self.slots[slotID].loaded = True

        # Check whether all players are loaded
        playing = 0
        loaded = 0
        for slot in self.slots:
            if slot.status == slotStatuses.PLAYING:
                if slot.loaded:
                    loaded += 1
                playing += 1

        if playing == loaded:
            self.allPlayersLoaded()

    def allPlayersLoaded(self) -> None:
        """
        Send allPlayersLoaded packet to every playing usr in match

        :return:
        """
        glob.streams.broadcast(self.playingStreamName, serverPackets.allPlayersLoaded)

    def playerSkip(self, userID: int) -> None:
        """
        Set a player skip status to True

        :param userID: ID of user
        :return:
        """
        slotID = self.getUserSlotID(userID)
        if slotID is None:
            return

        # Set skip to True
        self.slots[slotID].skip = True

        # Send skip packet to every playing user
        glob.streams.broadcast(self.playingStreamName, serverPackets.playerSkipped(slotID))

        # Check all skipped
        total_playing = 0
        skipped = 0
        for slot in self.slots:
            if slot.status == slotStatuses.PLAYING:
                if slot.skip:
                    skipped += 1
                total_playing += 1

        if total_playing == skipped:
            self.allPlayersSkipped()

    def allPlayersSkipped(self):
        """
        Send allPlayersSkipped packet to every playing usr in match

        :return:
        """
        glob.streams.broadcast(self.playingStreamName, serverPackets.allPlayersSkipped)

    def updateScore(self, slotID: int, score: int) -> None:
        """
        Update score for a slot

        :param slotID: the slot that the user that is updating their score is in
        :param score: the new score to update
        :return:
        """
        self.slots[slotID].score = score

    def updateHP(self, slotID: int, hp: int) -> None:
        """
        Update HP for a slot

        :param slotID: the slot that the user that is updating their hp is in
        :param hp: the new hp to update
        :return:
        """
        self.slots[slotID].failed = hp == 254

    def playerCompleted(self, userID: int) -> None:
        """
        Set userID's slot completed to True

        :param userID: ID of user
        """
        if (slotID := self.getUserSlotID(userID)) is None:
            return

        self.setSlot(slotID, complete = True)

        # Check all completed
        total_playing = 0
        completed = 0
        for slot in self.slots:
            if slot.status == slotStatuses.PLAYING:
                if slot.complete:
                    completed += 1
                total_playing += 1

        if total_playing == completed:
            self.allPlayersCompleted()

    def allPlayersCompleted(self) -> None:
        """
        Cleanup match stuff and send match end packet to everyone

        :return:
        """
        # Collect some info about the match that just ended to send to the api
        infoToSend = {
            "id": self.matchID,
            "name": self.matchName,
            "beatmap_id": self.beatmapID,
            "mods": self.mods,
            "game_mode": self.gameMode,
            "scores": {}
        }

        # Add score info for each player
        for slot in self.slots:
            if slot.user and slot.status == slotStatuses.PLAYING:
                infoToSend["scores"][glob.tokens.tokens[slot.user].userID] = {
                    "score": slot.score,
                    "mods": slot.mods,
                    "failed": slot.failed,
                    "pass": slot.passed,
                    "team": slot.team
                }

        # Send the info to the api
        glob.redis.publish("api:mp_complete_match", json.dumps(infoToSend)) # cant use orjson

        # Reset inProgress
        self.inProgress = False

        # Reset slots
        self.resetSlots()

        # Send match update
        self.sendUpdates()

        # Send match complete
        glob.streams.broadcast(self.streamName, serverPackets.matchComplete)

        # Destroy playing stream
        glob.streams.dispose(self.playingStreamName)
        glob.streams.remove(self.playingStreamName)

        # Console output
        #log.info("MPROOM{}: Match completed".format(self.matchID))

        chanName = f"#multi_{self.matchID}"

        if not self.bloodcatAlert:
            chat.sendMessage(glob.BOT_NAME, chanName, ' '.join([
                'In case you find any maps which are not available on',
                'osu!direct, remember we have a "!bloodcat" command',
                '(or "!q" if premium).'
            ]))
            self.bloodcatAlert = True

        # If this is a tournament match, then we send a notification in the chat
        # saying that the match has completed.
        if (
            self.isTourney and
            chanName in glob.channels.channels
        ):
            chat.sendMessage(glob.BOT_NAME, chanName, "Match has just finished.")
        return

    def resetSlots(self) -> None:
        for slot in self.slots:
            if (
                slot.user is not None and
                slot.status == slotStatuses.PLAYING
            ):
                slot.status = slotStatuses.NOT_READY
                slot.loaded = False
                slot.skip = False
                slot.complete = False
                slot.score = 0
                slot.failed = False
                slot.passed = True

    def getUserSlotID(self, userID: int) -> Optional[int]:
        """
        Get slot ID occupied by userID

        :return: slot id if found, None if user is not in room
        """
        for i, slot in enumerate(self.slots):
            if (
                slot.user and
                slot.user in glob.tokens.tokens and
                glob.tokens.tokens[slot.user].userID == userID
            ):
                return i

    def userJoin(self, user: token) -> bool:
        """
        Add someone to users in match

        :param user: user object of the user
        :return: True if join success, False if fail (room is full)
        """
        # Make sure we're not in this match
        for i, slot in enumerate(self.slots):
            if slot.user == user.token:
                # Set bugged slot to free
                self.setSlot(
                    slotID = i,
                    status = slotStatuses.FREE,
                    team = 0,
                    user = None,
                    mods = 0,
                    userID = -1
                )

        # Find first free slot
        for i, slot in enumerate(self.slots):
            if slot.status == slotStatuses.FREE:
                # Occupy slot
                team = matchTeams.NO_TEAM
                if (
                    self.matchTeamType == matchTeamTypes.TEAM_VS or
                    self.matchTeamType == matchTeamTypes.TAG_TEAM_VS
                ):
                    team = matchTeams.RED if i % 2 == 0 else matchTeams.BLUE

                self.setSlot(
                    slotID = i,
                    status = slotStatuses.NOT_READY,
                    team = team,
                    user = user.token,
                    mods = 0,
                    userID = user.userID
                )

                if user.staff:
                    self.add_referee(user.userID)

                # Send updated match data
                self.sendUpdates()
                return True

        if user.staff: # Allow mods+ to join into locked but empty slots.
            for i, slot in enumerate(self.slots):
                if (
                    slot.status == slotStatuses.LOCKED and
                    slot.userID == -1
                ):
                    if self.matchTeamType in (
                        matchTeamTypes.TEAM_VS,
                        matchTeamTypes.TAG_TEAM_VS
                    ):
                        team = matchTeams.RED if i % 2 == 0 else matchTeams.BLUE
                    else:
                        team = matchTeams.NO_TEAM

                    self.setSlot(
                        slotID = i,
                        status = slotStatuses.NOT_READY,
                        team = team,
                        user = user.token,
                        mods = 0,
                        userID = user.userID
                    )

                    # Send updated match data
                    self.sendUpdates()
                    return True

        return False

    def userLeft(self, user, disposeMatch: bool = True) -> None:
        """
        Remove someone from users in match

        :param user: user object of the user
        :param disposeMatch: if `True`, will try to dispose match if there are no users in the room
        :return:
        """
        # Make sure the user is in room
        slotID = self.getUserSlotID(user.userID)
        if slotID is None:
            return

        # Set that slot to free
        self.setSlot(
            slotID = slotID,
            status = slotStatuses.FREE,
            team = 0,
            user = None,
            mods = 0,
            userID = -1
        )

        # Check if everyone left
        if self.countUsers() == 0 and disposeMatch and not self.isTourney:
            # Dispose match
            glob.matches.disposeMatch(self.matchID)
            #log.info("MPROOM{}: Room disposed because all users left.".format(self.matchID))
            return

        # Check if host left
        if user.userID == self.hostUserID:
            # Give host to someone else
            for slot in self.slots:
                if (
                    slot.user and
                    slot.user in glob.tokens.tokens
                ):
                    self.setHost(glob.tokens.tokens[slot.user].userID)
                    break

        # Send updated match data
        self.sendUpdates()

    def userChangeSlot(self, userID: int, newSlotID: int) -> bool:
        """
        Change userID slot to newSlotID

        :param userID: user that changed slot
        :param newSlotID: slot id of new slot
        :return:
        """

        # Make sure the match is not locked
        if self.isLocked or self.isStarting:
            return False

        # Make sure the user is in room
        oldSlotID = self.getUserSlotID(userID)
        if oldSlotID is None:
            return False

        # Make sure there is no one inside new slot
        if (
            self.slots[newSlotID].user is not None or
            self.slots[newSlotID].status != slotStatuses.FREE
        ):
            return False

        # Get old slot data
        #oldData = dill.copy(self.slots[oldSlotID])
        oldData = deepcopy(self.slots[oldSlotID])

        # Free old slot
        self.setSlot(
            slotID = oldSlotID,
            status = slotStatuses.FREE,
            team = 0,
            user = None,
            mods = 0,
            loaded = False,
            skip = False,
            complete = False,
            userID = -1
        )

        # Occupy new slot
        self.setSlot(
            slotID = newSlotID,
            status = oldData.status,
            team = oldData.team,
            user = oldData.user,
            mods = oldData.mods,
            userID = oldData.userID
        )

        # Send updated match data
        self.sendUpdates()

        return True

    def changePassword(self, newPassword: str) -> None:
        """
        Change match password to newPassword

        :param newPassword: new password string
        :return:
        """
        self.matchPassword = newPassword

        # Send password change to every user in match
        glob.streams.broadcast(self.streamName, serverPackets.changeMatchPassword(self.matchPassword))

        # Send new match settings too
        self.sendUpdates()

    def changeMods(self, mods: int) -> None:
        """
        Set match global mods

        :param mods: mods bitwise int thing
        :return:
        """
        # Set new mods and send update
        self.mods = mods
        self.sendUpdates()

    def userHasBeatmap(self, userID: int, has: bool = True) -> None:
        """
        Set no beatmap status for userID

        :param userID: ID of user
        :param has: True if has beatmap, false if not
        :return:
        """
        # Make sure the user is in room
        slotID = self.getUserSlotID(userID)
        if slotID is None:
            return

        # Set slot
        self.setSlot(slotID, slotStatuses.NOT_READY if has else slotStatuses.NO_MAP)

        # Send updates
        self.sendUpdates()

    def transferHost(self, slotID: int) -> None:
        """
        Transfer host to slotID

        :param slotID: ID of slot
        :return:
        """
        slot = self.slots[slotID]

        # Make sure there is someone in that slot
        if (
            not slot.user or
            slot.user not in glob.tokens.tokens
        ):
            return

        # Transfer host
        self.setHost(glob.tokens.tokens[slot.user].userID)

    def playerFailed(self, userID: int) -> None:
        """
        Send userID's failed packet to everyone in match

        :param userID: ID of user
        :return:
        """
        # Make sure the user is in room
        slotID = self.getUserSlotID(userID)
        if slotID is None:
            return

        self.slots[slotID].passed = False

        # Send packet to everyone
        glob.streams.broadcast(self.playingStreamName, serverPackets.playerFailed(slotID))

    def invite(self, fro: int, to: int) -> None:
        """
        Fro invites to in this match.

        :param fro: sender userID
        :param to: receiver userID
        :return:
        """
        # Get tokens
        froToken = glob.tokens.getTokenFromUserID(fro, _all=False)
        toToken = glob.tokens.getTokenFromUserID(to, _all=False)
        if not froToken or not toToken:
            return

        # Aika is too busy
        if to == 999:
            chat.sendMessage(
                glob.BOT_NAME, froToken.username,
                "I'd love to join your match, but I've got a job to do!.")
            return

        # Send message
        pw_safe = self.matchPassword.replace(' ', '_')
        message = (
            'Come join my multiplayer match: '
            f'"[osump://{self.matchID}/{pw_safe} {self.matchName}]"'
        )
        chat.sendMessage(token=froToken, to=toToken.username, message=message)

    def countUsers(self) -> int:
        """
        Return how many players are in that match

        :return: number of users
        """
        return sum(1 for slot in self.slots if slot.user is not None)

    def changeTeam(self, userID: int, newTeam: Optional[int] = None) -> None:
        """
        Change userID's team

        :param userID: id of user
        :return:
        """
        # Make sure this match's mode has teams
        if (
            self.matchTeamType != matchTeamTypes.TEAM_VS and
            self.matchTeamType != matchTeamTypes.TAG_TEAM_VS
        ):
            return

        # Make sure the match is not locked
        if self.isLocked or self.isStarting:
            return

        # Make sure the user is in room
        slotID = self.getUserSlotID(userID)
        if slotID is None:
            return

        # Update slot and send update
        if newTeam is None:
            if self.slots[slotID].team == matchTeams.RED:
                newTeam = matchTeams.BLUE
            else:
                newTeam = matchTeams.RED

            self.setSlot(slotID, None, newTeam)
        self.sendUpdates()

    def sendUpdates(self) -> None:
        """
        Send match updates packet to everyone in lobby and room streams

        :return:
        """
        self.matchDataCache = serverPackets.updateMatch(self.matchID)
        censoredDataCache = serverPackets.updateMatch(self.matchID, censored=True)
        if self.matchDataCache:
            glob.streams.broadcast(self.streamName, self.matchDataCache)
        if censoredDataCache:
            glob.streams.broadcast("lobby", censoredDataCache)
        else:
            log.error(f"MPROOM{self.matchID}: Can't send match update packet, match data is None!!!")

    def checkTeams(self) -> bool:
        """
        Check if match teams are valid

        :return: True if valid, False if invalid
        :return:
        """
        if self.matchTeamType != matchTeamTypes.TEAM_VS and self.matchTeamType != matchTeamTypes.TAG_TEAM_VS:
            # Teams are always valid if we have no teams
            return True

        # We have teams, check if they are valid
        firstTeam = -1

        for slot in self.slots:
            if slot.user and (slot.status & slotStatuses.NO_MAP) == 0:
                if firstTeam == -1:
                    firstTeam = slot.team
                elif firstTeam != slot.team:
                    return True

        log.warning(f"MPROOM{self.matchID}: Invalid teams!")
        return False

    def start(self) -> bool:
        """
        Start the match

        :return:
        """
        # Remove isStarting timer flag thingie
        self.isStarting = False

        # Make sure we have enough players
        if not self.checkTeams():
            return False

        # Create playing channel
        glob.streams.add(self.playingStreamName)

        # Change inProgress value
        self.inProgress = True

        # Set playing to ready players and set load, skip and complete to False
        # Make clients join playing stream
        for slot in self.slots:
            if slot.user is None:
                continue

            if slot.user in glob.tokens.tokens:
                slot.status = slotStatuses.PLAYING
                slot.loaded = False
                slot.skip = False
                slot.complete = False

                user_token = glob.tokens.tokens[slot.user]
                user_token.joinStream(self.playingStreamName)

        # Send match start packet
        glob.streams.broadcast(self.playingStreamName, serverPackets.matchStart(self.matchID))

        # Send updates
        self.sendUpdates()
        return True

    def forceSize(self, matchSize: int) -> None:
        for i in range(matchSize):
            if self.slots[i].status == slotStatuses.LOCKED:
                self.toggleSlotLocked(i)
        for i in range(matchSize, 16):
            if self.slots[i].status != slotStatuses.LOCKED:
                self.toggleSlotLocked(i)

    def abort(self) -> None:
        if not self.inProgress:
            log.warning(f"MPROOM{self.matchID}: Match is not in progress!")
            return
        self.inProgress = False
        self.isStarting = False
        self.resetSlots()
        self.sendUpdates()
        glob.streams.broadcast(self.playingStreamName, serverPackets.matchAbort)
        glob.streams.dispose(self.playingStreamName)
        glob.streams.remove(self.playingStreamName)

    def initializeTeams(self) -> None:
        if self.matchTeamType in {matchTeamTypes.TEAM_VS, matchTeamTypes.TAG_TEAM_VS}:
            # Set teams
            for i, _slot in enumerate(self.slots):
                _slot.team = matchTeams.RED if i % 2 == 0 else matchTeams.BLUE
        else:
            # Reset teams
            for _slot in self.slots:
                _slot.team = matchTeams.NO_TEAM

    def resetMods(self) -> None:
        for _slot in self.slots:
            _slot.mods = 0

    def resetReady(self) -> None:
        for _slot in self.slots:
            if _slot.status == slotStatuses.READY:
                _slot.status = slotStatuses.NOT_READY

    def sendReadyStatus(self) -> None:
        chanName = f"#multi_{self.matchID}"

        # Make sure match exists before attempting to do anything else
        if chanName not in glob.channels.channels:
            return

        totalUsers = 0
        readyUsers = 0

        for slot in self.slots:
            # Make sure there is a user in this slot
            if slot.user is None:
                continue

            # In this slot there is a user, so we increase the amount of total users
            # in this multi room.
            totalUsers += 1

            if slot.status == slotStatuses.READY:
                readyUsers += 1

        if totalUsers == 0:
            message = 'The match is now empty.'
        else:
            message = [f"{readyUsers} users ready out of {totalUsers}."]
            if totalUsers == readyUsers:
                message.append('All users ready!')

            message = ' '.join(message)

        chat.sendMessage(glob.BOT_NAME, chanName, message)

    def __enter__(self) -> 'match':
        # 🌚🌚🌚🌚🌚
        self._lock.acquire()
        return self

    def __exit__(self, exc_type: Optional[Type[BaseException]],
                 exc_value: Optional[BaseException],
                 traceback: Optional[TracebackType]) -> None:
        self._lock.release()
