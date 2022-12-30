from __future__ import annotations

import json
from copy import deepcopy
from threading import Lock
from typing import Optional

from common.log import logUtils as log
from constants import dataTypes
from constants import matchModModes
from constants import matchTeams
from constants import matchTeamTypes
from constants import serverPackets
from constants import slotStatuses
from helpers import chatHelper as chat
from objects import glob
from objects.osuToken import token
from objects import streamList
from objects import channelList, slot
from typing import TypedDict

# (set) bancho:matches
# (json obj) bancho:matches:{match_id}
# (set? list?) bancho:matches:{match_id}:slots
# (json obj) bancho:matches:{match_id}:slots:{index}
# (set) bancho:matches:{match_id}:referees



class Match(TypedDict):
    match_id: int
    match_name: str
    match_password: str
    beatmap_id: int
    beatmap_name: str
    beatmap_md5: str
    game_mode: int
    host_user_id: int
    mods: int
    match_scoring_type: int # matchScoringTypes
    match_team_type: int # matchTeamTypes
    match_mod_mode: int # matchModModes
    seed: int
    is_tourney: bool
    is_locked: bool
    is_starting: bool
    is_in_progress: bool
    creation_time: float

    # now separate
    # slots: list[slot.Slot]
    # referees: set[int]


def make_key(match_id: int) -> str:
    return f"bancho:matches:{match_id}"


def create_match(
    match_name: str,
    match_password: str,
    beatmap_id: int,
    beatmap_name: str,
    beatmap_md5: str,
    game_mode: int,
    host_user_id: int,
    mods: int,
    match_scoring_type: int,
    match_team_type: int,
    match_mod_mode: int,
    seed: int,
    is_tourney: bool,
    is_locked: bool,
    is_starting: bool,
    is_in_progress: bool,
    creation_time: float,
) -> Match:
    match_id = glob.redis.incr("bancho:matches:last_id")
    glob.redis.sadd("bancho:matches", match_id)
    for slot_id in range(16):
        slot.create_slot(match_id, slot_id)
    match: Match = {
        "match_id": match_id,
        "match_name": match_name,
        "match_password": match_password,
        "beatmap_id": beatmap_id,
        "beatmap_name": beatmap_name,
        "beatmap_md5": beatmap_md5,
        "game_mode": game_mode,
        "host_user_id": host_user_id,
        "mods": mods,
        "match_scoring_type": match_scoring_type,
        "match_team_type": match_team_type,
        "match_mod_mode": match_mod_mode,
        "seed": seed,
        "is_tourney": is_tourney,
        "is_locked": is_locked,
        "is_starting": is_starting,
        "is_in_progress": is_in_progress,
        "creation_time": creation_time,
    }
    glob.redis.set(make_key(match_id), json.dumps(match))
    return match


def get_match_ids() -> set[int]:
    raw_match_ids = glob.redis.smembers("bancho:matches")
    return {int(match_id) for match_id in raw_match_ids}


def get_match(match_id: int) -> Optional[Match]:
    raw_match = glob.redis.get(make_key(match_id))
    if raw_match is None:
        return None

    return json.loads(raw_match)


def update_match(
    match_id: int,
    match_name: Optional[str] = None,
    match_password: Optional[str] = None,
    beatmap_id: Optional[int] = None,
    beatmap_name: Optional[str] = None,
    beatmap_md5: Optional[str] = None,
    game_mode: Optional[int] = None,
    host_user_id: Optional[int] = None,
    mods: Optional[int] = None,
    match_scoring_type: Optional[int] = None,
    match_team_type: Optional[int] = None,
    match_mod_mode: Optional[int] = None,
    seed: Optional[int] = None,
    is_tourney: Optional[bool] = None,
    is_locked: Optional[bool] = None,
    is_starting: Optional[bool] = None,
    is_in_progress: Optional[bool] = None,
    creation_time: Optional[float] = None,
) -> Optional[Match]:
    match = get_match(match_id)
    if match is None:
        return

    if match_name is not None:
        match["match_name"] = match_name
    if match_password is not None:
        match["match_password"] = match_password
    if beatmap_id is not None:
        match["beatmap_id"] = beatmap_id
    if beatmap_name is not None:
        match["beatmap_name"] = beatmap_name
    if beatmap_md5 is not None:
        match["beatmap_md5"] = beatmap_md5
    if game_mode is not None:
        match["game_mode"] = game_mode
    if host_user_id is not None:
        match["host_user_id"] = host_user_id
    if mods is not None:
        match["mods"] = mods
    if match_scoring_type is not None:
        match["match_scoring_type"] = match_scoring_type
    if match_team_type is not None:
        match["match_team_type"] = match_team_type
    if match_mod_mode is not None:
        match["match_mod_mode"] = match_mod_mode
    if seed is not None:
        match["seed"] = seed
    if is_tourney is not None:
        match["is_tourney"] = is_tourney
    if is_locked is not None:
        match["is_locked"] = is_locked
    if is_starting is not None:
        match["is_starting"] = is_starting
    if is_in_progress is not None:
        match["is_in_progress"] = is_in_progress
    if creation_time is not None:
        match["creation_time"] = creation_time

    glob.redis.set(make_key(match_id), json.dumps(match))
    return match


def delete_match(match_id: int) -> None:
    # TODO: should we throw error when no match exists?
    glob.redis.srem("bancho:matches", match_id)
    glob.redis.delete(make_key(match_id))

    # TODO: should devs have to do this separately?
    slot.delete_slots(match_id)

def create_stream_name(match_id: int) -> str:
    return f"multi/{match_id}"

def create_playing_stream_name(match_id: int) -> str:
    return f"multi/{match_id}/playing"

def getMatchData(match_id: int, censored: bool = False) -> tuple[tuple[object, int]]:
    """
    Return binary match data structure for packetHelper

    :param match_id: Match ID
    :param censored: Whether to censor password
    :return:
    """
    # General match info

    multiplayer_match = get_match(match_id)
    assert multiplayer_match is not None

    slots = slot.get_slots(match_id)
    assert len(slots) == 16

    struct = [
        (multiplayer_match["match_id"], dataTypes.UINT16),
        (int(multiplayer_match["is_in_progress"]), dataTypes.BYTE),
        (0, dataTypes.BYTE), # TODO: what is this?
        (multiplayer_match["mods"], dataTypes.UINT32),
        (multiplayer_match["match_name"], dataTypes.STRING),
    ]
    if censored and multiplayer_match["match_password"]:
        struct.append(("redacted", dataTypes.STRING))
    else:
        struct.append((multiplayer_match["match_password"], dataTypes.STRING))

    struct.extend(
        [
            (multiplayer_match["beatmap_name"], dataTypes.STRING),
            (multiplayer_match["beatmap_id"], dataTypes.UINT32),
            (multiplayer_match["beatmap_md5"], dataTypes.STRING),
        ],
    )

    struct.extend([(slot["status"], dataTypes.BYTE) for slot in slots])
    struct.extend([(slot["team"], dataTypes.BYTE) for slot in slots])

    struct.extend(
        [
            (glob.tokens.tokens[slot["user_token"]].userID, dataTypes.UINT32)
            for slot in slots
            if (slot["user_token"] and slot["user_token"] in glob.tokens.tokens)
        ],
    )

    # Other match data
    struct.extend(
        [
            (multiplayer_match["host_user_id"], dataTypes.SINT32),
            (multiplayer_match["game_mode"], dataTypes.BYTE),
            (multiplayer_match["match_scoring_type"], dataTypes.BYTE),
            (multiplayer_match["match_team_type"], dataTypes.BYTE),
            (multiplayer_match["match_mod_mode"], dataTypes.BYTE),
        ],
    )

    # Slot mods if free mod is enabled
    if multiplayer_match["match_mod_mode"] == matchModModes.FREE_MOD:
        struct.extend([(slot["mods"], dataTypes.UINT32) for slot in slots])

    # Seed idk
    # TODO: Implement this, it should be used for mania "random" mod
    struct.append((multiplayer_match["seed"], dataTypes.UINT32))

    return tuple(struct)

def setHost(match_id: int, newHostID: int) -> bool:
    """
    Set room host to newHost and send him host packet

    :param match_id: match id
    :param newHost: new host userID
    :return:
    """

    multiplayer_match = get_match(match_id)
    assert multiplayer_match is not None

    old_host = glob.tokens.getTokenFromUserID(multiplayer_match["host_user_id"])
    assert old_host is not None

    if not old_host.staff:
        remove_referee(match_id, multiplayer_match["host_user_id"])

    add_referee(match_id, newHostID)

    slot_id = getUserSlotID(match_id, newHostID)
    if slot_id is None:
        return False

    _slot = slot.get_slot(match_id, slot_id)
    assert _slot is not None
    if _slot["user_token"] is None or _slot["user_token"] not in glob.tokens.tokens:
        return False

    multiplayer_match["host_user_id"] = newHostID

    user_token = glob.tokens.tokens[_slot["user_token"]]
    user_token.enqueue(serverPackets.matchTransferHost)
    sendUpdates(match_id)
    return True

def removeHost(match_id: int) -> None:
    """
    Removes the host (for tourney matches)

    :param match_id: match id
    :return:
    """

    multiplayer_match = get_match(match_id)
    assert multiplayer_match is not None

    remove_referee(match_id, multiplayer_match["host_user_id"])

    update_match(match_id, host_user_id=-1)

    sendUpdates(match_id)

# TODO: this func probably should not exist; jkurwa
def setSlot(
    match_id: int,
    slot_id: int,
    status: Optional[int] = None,
    team: Optional[int] = None,
    user_id: Optional[int] = None,
    user_token: Optional[str] = "", # TODO: need to refactor stuff for this
    mods: Optional[int] = None,
    loaded: Optional[bool] = None,
    skip: Optional[bool] = None,
    complete: Optional[bool] = None,
) -> slot.Slot:
    _slot = slot.get_slot(match_id, slot_id)
    assert _slot is not None

    _slot = slot.update_slot(
        match_id,
        slot_id,
        status=status,
        team=team,
        user_id=user_id,
        user_token=user_token,
        mods=mods,
        loaded=loaded,
        skip=skip,
        complete=complete,
    )
    assert _slot is not None
    return _slot

def setSlotMods(match_id: int, slot_id: int, mods: int) -> None:
    """
    Set slotID mods. Same as calling setSlot and then sendUpdate

    :param slotID: slot number
    :param mods: new mods
    :return:
    """
    # Set new slot data and send update
    setSlot(match_id, slot_id, mods=mods)
    sendUpdates(match_id)

def toggleSlotReady(match_id: int, slot_id: int) -> None:
    """
    Switch slotID ready/not ready status
    Same as calling setSlot and then sendUpdate

    :param slotID: slot number
    :return:
    """

    multiplayer_match = get_match(match_id)
    assert multiplayer_match is not None

    _slot = slot.get_slot(match_id, slot_id)
    assert _slot is not None

    # Update ready status and setnd update
    if not _slot["user_token"] or multiplayer_match["is_starting"]:
        return

    oldStatus = _slot["status"]
    if oldStatus == slotStatuses.READY:
        newStatus = slotStatuses.NOT_READY
    else:
        newStatus = slotStatuses.READY

    setSlot(match_id, slot_id, newStatus)
    sendUpdates(match_id)

def toggleSlotLocked(match_id: int, slot_id: int) -> None:
    """
    Lock a slot
    Same as calling setSlot and then sendUpdate

    :param slotID: slot number
    :return:
    """

    _slot = slot.get_slot(match_id, slot_id)
    assert _slot is not None

    # Check if slot is already locked
    if _slot["status"] == slotStatuses.LOCKED:
        newStatus = slotStatuses.FREE
    else:
        newStatus = slotStatuses.LOCKED

    # Send updated settings to kicked user, so he returns to lobby
    if _slot["user_token"] and _slot["user_token"] in glob.tokens.tokens:
        packet_data = serverPackets.updateMatch(match_id)
        if packet_data is None:
            # TODO: is this correct behaviour?
            # ripple was doing this before the stateless refactor,
            # but i'm pretty certain the osu! client won't like this.
            glob.tokens.tokens[_slot["user_token"]].enqueue(b"")
            return None

        glob.tokens.tokens[_slot["user_token"]].enqueue(packet_data)

    # Set new slot status
    setSlot(
        match_id,
        slot_id=slot_id,
        status=newStatus,
        team=0,
        user_token=None,
        mods=0,
        user_id=-1,
    )

    # Send updates to everyone else
    sendUpdates(match_id)

def playerLoaded(match_id: int, user_id: int) -> None:
    """
    Set a player loaded status to True

    :param userID: ID of user
    :return:
    """
    slot_id = getUserSlotID(match_id, user_id)
    if slot_id is None:
        return

    # Set loaded to True
    _slot = slot.get_slot(match_id, slot_id)
    assert _slot is not None

    _slot = slot.update_slot(match_id, slot_id, loaded=True)
    assert _slot is not None

    slots = slot.get_slots(match_id)
    assert len(slots) == 16

    # Check whether all players are loaded
    playing = 0
    loaded = 0
    for __slot in slots:
        if __slot["status"] == slotStatuses.PLAYING:
            if __slot["loaded"]:
                loaded += 1
            playing += 1

    if playing == loaded:
        allPlayersLoaded(match_id)

def allPlayersLoaded(match_id: int) -> None:
    """
    Send allPlayersLoaded packet to every playing usr in match

    :return:
    """
    multiplayer_match = get_match(match_id)
    assert multiplayer_match is not None

    playing_stream_name = create_playing_stream_name(match_id)
    streamList.broadcast(playing_stream_name, serverPackets.allPlayersLoaded)

def playerSkip(match_id: int, user_id: int) -> None:
    """
    Set a player skip status to True

    :param userID: ID of user
    :return:
    """
    slot_id = getUserSlotID(match_id, user_id)
    if slot_id is None:
        return

    _slot = slot.get_slot(match_id, slot_id)
    assert _slot is not None

    # Set skip to True
    _slot = slot.update_slot(match_id, slot_id, skip=True)
    assert _slot is not None

    # Send skip packet to every playing user
    playing_stream_name = create_playing_stream_name(match_id)
    packet_data = serverPackets.playerSkipped(slot_id)
    streamList.broadcast(playing_stream_name, packet_data)

    slots = slot.get_slots(match_id)
    assert len(slots) == 16

    # Check all skipped
    total_playing = 0
    skipped = 0
    for __slot in slots:
        if __slot["status"] == slotStatuses.PLAYING:
            if __slot["skip"]:
                skipped += 1
            total_playing += 1

    if total_playing == skipped:
        allPlayersSkipped(match_id)

def allPlayersSkipped(match_id):
    """
    Send allPlayersSkipped packet to every playing usr in match

    :return:
    """

    playing_stream_name = create_playing_stream_name(match_id)
    streamList.broadcast(playing_stream_name, serverPackets.allPlayersSkipped)

def updateScore(match_id: int, slot_id: int, score: int) -> None:
    """
    Update score for a slot

    :param slotID: the slot that the user that is updating their score is in
    :param score: the new score to update
    :return:
    """
    _slot = slot.get_slot(match_id, slot_id)
    assert _slot is not None

    _slot = slot.update_slot(match_id, slot_id, score=score)
    assert _slot is not None

def updateHP(match_id: int, slot_id: int, hp: int) -> None:
    """
    Update HP for a slot

    :param slotID: the slot that the user that is updating their hp is in
    :param hp: the new hp to update
    :return:
    """
    _slot = slot.get_slot(match_id, slot_id)
    assert _slot is not None

    failed = hp == 254

    _slot = slot.update_slot(match_id, slot_id, failed=failed)
    assert _slot is not None


def playerCompleted(match_id: int, user_id: int) -> None:
    """
    Set userID's slot completed to True

    :param userID: ID of user
    """
    slot_id = getUserSlotID(match_id, user_id)
    if slot_id is None:
        return

    setSlot(match_id, slot_id, complete=True)

    slots = slot.get_slots(match_id)
    assert len(slots) == 16

    # Check all completed
    total_playing = 0
    completed = 0
    for _slot in slots:
        if _slot["status"] == slotStatuses.PLAYING:
            if _slot["complete"]:
                completed += 1
            total_playing += 1

    if total_playing == completed:
        allPlayersCompleted(match_id)

def allPlayersCompleted(match_id: int) -> None:
    """
    Cleanup match stuff and send match end packet to everyone

    :return:
    """
    multiplayer_match = get_match(match_id)
    assert multiplayer_match is not None

    # Collect some info about the match that just ended to send to the api
    infoToSend = {
        "id": multiplayer_match["match_id"],
        "name": multiplayer_match["match_name"],
        "beatmap_id": multiplayer_match["beatmap_id"],
        "mods": multiplayer_match["mods"],
        "game_mode": multiplayer_match["game_mode"],
        "scores": {},
    }

    slots = slot.get_slots(match_id)
    assert len(slots) == 16

    # Add score info for each player
    for _slot in slots:
        if _slot["user_token"] and _slot["status"] == slotStatuses.PLAYING:
            infoToSend["scores"][glob.tokens.tokens[_slot["user_token"]].userID] = {
                "score": _slot["score"],
                "mods": _slot["mods"],
                "failed": _slot["failed"],
                "pass": _slot["passed"],
                "team": _slot["team"],
            }

    # Send the info to the api
    glob.redis.publish(
        "api:mp_complete_match",
        json.dumps(infoToSend),
    )  # cant use orjson

    # Reset inProgress
    multiplayer_match = update_match(match_id, is_in_progress=False)
    assert multiplayer_match is not None

    # Reset slots
    resetSlots(match_id)

    # Send match update
    sendUpdates(match_id)

    # Send match complete
    stream_name = create_stream_name(match_id)
    streamList.broadcast(stream_name, serverPackets.matchComplete)

    # Destroy playing stream
    playing_stream_name = create_playing_stream_name(match_id)
    streamList.dispose(playing_stream_name)
    streamList.remove(playing_stream_name)

    # Console output
    # log.info("MPROOM{}: Match completed".format(self.matchID))

    channel_name = f"#multi_{match_id}"

    # If this is a tournament match, then we send a notification in the chat
    # saying that the match has completed.
    if multiplayer_match["is_tourney"] and channel_name in channelList.getChannelNames():
        chat.sendMessage(glob.BOT_NAME, channel_name, "Match has just finished.")


def resetSlots(match_id: int) -> None:
    slots = slot.get_slots(match_id)
    assert len(slots) == 16

    # TODO: make sure slot_id is right?
    # not sure about the order.
    # also not sure we start from 0.
    for slot_id, _slot in enumerate(slots):
        if _slot["user_token"] is not None and _slot["status"] == slotStatuses.PLAYING:
            slot.update_slot(
                match_id,
                slot_id,
                status=slotStatuses.NOT_READY,
                loaded=False,
                skip=False,
                complete=False,
                score=0,
                failed=False,
                passed=True,
            )

def getUserSlotID(match_id: int, user_id: int) -> Optional[int]:
    """
    Get slot ID occupied by userID

    :return: slot id if found, None if user is not in room
    """
    slots = slot.get_slots(match_id)
    assert len(slots) == 16

    for slot_id, _slot in enumerate(slots):
        if (
            _slot["user_token"]
            and _slot["user_token"] in glob.tokens.tokens
            and glob.tokens.tokens[_slot["user_token"]].userID == user_id
        ):
            return slot_id

def userJoin(match_id: int, user_token_obj: token) -> bool:
    """
    Add someone to users in match

    :param user: user object of the user
    :return: True if join success, False if fail (room is full)
    """
    multiplayer_match = get_match(match_id)
    assert multiplayer_match is not None

    slots = slot.get_slots(match_id)
    breakpoint()
    assert len(slots) == 16

    # Make sure we're not in this match
    for slot_id, _slot in enumerate(slots):
        if _slot["user_token"] == user_token_obj.token:
            # Set bugged slot to free
            setSlot(
                match_id,
                slot_id,
                status=slotStatuses.FREE,
                team=0,
                user_token=None,
                mods=0,
                user_id=-1,
            )
            break

    # Find first free slot
    for slot_id, _slot in enumerate(slots):
        if _slot["status"] == slotStatuses.FREE:
            # Occupy slot
            team = matchTeams.NO_TEAM
            if (
                multiplayer_match["match_team_type"] == matchTeamTypes.TEAM_VS
                or multiplayer_match["match_team_type"] == matchTeamTypes.TAG_TEAM_VS
            ):
                team = matchTeams.RED if slot_id % 2 == 0 else matchTeams.BLUE

            setSlot(
                match_id,
                slot_id,
                status=slotStatuses.NOT_READY,
                team=team,
                user_token=user_token_obj.token,
                mods=0,
                user_id=user_token_obj.userID,
            )

            if user_token_obj.staff:
                add_referee(match_id, user_token_obj.userID)

            # Send updated match data
            sendUpdates(match_id)
            return True

    if user_token_obj.staff:  # Allow mods+ to join into locked but empty slots.
        for slot_id, _slot in enumerate(slots):
            if _slot["status"] == slotStatuses.LOCKED and _slot["user_id"] == -1:
                if multiplayer_match["match_team_type"] in (
                    matchTeamTypes.TEAM_VS,
                    matchTeamTypes.TAG_TEAM_VS,
                ):
                    team = matchTeams.RED if slot_id % 2 == 0 else matchTeams.BLUE
                else:
                    team = matchTeams.NO_TEAM

                setSlot(
                    match_id,
                    slot_id,
                    status=slotStatuses.NOT_READY,
                    team=team,
                    user_token=user_token_obj.token,
                    mods=0,
                    user_id=user_token_obj.userID,
                )

                # Send updated match data
                sendUpdates(match_id)
                return True

    return False

def userLeft(match_id: int, user: token, disposeMatch: bool = True) -> None:
    """
    Remove someone from users in match

    :param user: user object of the user
    :param disposeMatch: if `True`, will try to dispose match if there are no users in the room
    :return:
    """
    multiplayer_match = get_match(match_id)
    assert multiplayer_match is not None

    # Make sure the user is in room
    slot_id = getUserSlotID(match_id, user.userID)
    if slot_id is None:
        return

    # Set that slot to free
    setSlot(
        match_id,
        slot_id,
        status=slotStatuses.FREE,
        team=0,
        user_token=None,
        mods=0,
        user_id=-1,
    )

    # Check if everyone left
    if countUsers(match_id) == 0 and disposeMatch and not multiplayer_match["is_tourney"]:
        # Dispose match
        glob.matches.disposeMatch(multiplayer_match["match_id"])
        # log.info("MPROOM{}: Room disposed because all users left.".format(self.matchID))
        return

    slots = slot.get_slots(match_id)
    assert len(slots) == 16

    # Check if host left
    if user.userID == multiplayer_match["host_user_id"]:
        # Give host to someone else
        for _slot in slots:
            if _slot["user_token"] and _slot["user_token"] in glob.tokens.tokens:
                setHost(match_id, glob.tokens.tokens[_slot["user_token"]].userID)
                break

    # Send updated match data
    sendUpdates(match_id)

def userChangeSlot(match_id: int, user_id: int, new_slot_id: int) -> bool:
    """
    Change userID slot to newSlotID

    :param userID: user that changed slot
    :param newSlotID: slot id of new slot
    :return:
    """

    multiplayer_match = get_match(match_id)
    assert multiplayer_match is not None

    slots = slot.get_slots(match_id)
    assert len(slots) == 16

    # Make sure the match is not locked
    if multiplayer_match["is_locked"] or multiplayer_match["is_starting"]:
        return False

    # Make sure the user is in room
    old_slot_id = getUserSlotID(match_id, user_id)
    if old_slot_id is None:
        return False

    # Make sure there is no one inside new slot
    if (
        slots[new_slot_id]["user_token"] is not None
        or slots[new_slot_id]["status"] != slotStatuses.FREE
    ):
        return False

    # Get old slot data
    # TODO: do we need to deepcopy this after the stateless refactor?
    # old_data = dill.copy(self.slots[oldSlotID])
    old_data = deepcopy(slots[old_slot_id])

    # Free old slot
    setSlot(
        match_id,
        old_slot_id,
        status=slotStatuses.FREE,
        team=0,
        user_token=None,
        mods=0,
        loaded=False,
        skip=False,
        complete=False,
        user_id=-1,
    )

    # Occupy new slot
    setSlot(
        match_id,
        new_slot_id,
        status=old_data["status"],
        team=old_data["team"],
        user_token=old_data["user_token"],
        mods=old_data["mods"],
        user_id=old_data["user_id"],
    )

    # Send updated match data
    sendUpdates(match_id)

    return True

def changePassword(match_id: int, newPassword: str) -> None:
    """
    Change match password to newPassword

    :param newPassword: new password string
    :return:
    """
    multiplayer_match = get_match(match_id)
    assert multiplayer_match is not None

    multiplayer_match = update_match(match_id, match_password=newPassword)
    assert multiplayer_match is not None

    # Send password change to every user in match
    streamList.broadcast(
        create_stream_name(match_id),
        serverPackets.changeMatchPassword(multiplayer_match["match_password"]),
    )

    # Send new match settings too
    sendUpdates(match_id)

def changeMods(match_id: int, mods: int) -> None:
    """
    Set match global mods

    :param mods: mods bitwise int thing
    :return:
    """
    multiplayer_match = get_match(match_id)
    assert multiplayer_match is not None

    # Set new mods and send update
    multiplayer_match = update_match(match_id, mods=mods)
    assert multiplayer_match is not None

    sendUpdates(match_id)

def userHasBeatmap(match_id: int, user_id: int, has_beatmap: bool = True) -> None:
    """
    Set no beatmap status for userID

    :param userID: ID of user
    :param has: True if has beatmap, false if not
    :return:
    """
    # Make sure the user is in room
    slot_id = getUserSlotID(match_id, user_id)
    if slot_id is None:
        return

    # Set slot
    if has_beatmap:
        new_status = slotStatuses.NOT_READY
    else:
        new_status = slotStatuses.NO_MAP

    setSlot(match_id, slot_id, new_status)

    # Send updates
    sendUpdates(match_id)

def transferHost(match_id: int, slot_id: int) -> None:
    """
    Transfer host to slotID

    :param slotID: ID of slot
    :return:
    """
    _slot = slot.get_slot(match_id, slot_id)
    assert _slot is not None

    # Make sure there is someone in that slot
    if not _slot["user_token"] or _slot["user_token"] not in glob.tokens.tokens:
        return

    # Transfer host
    setHost(match_id, glob.tokens.tokens[_slot["user_token"]].userID)

def playerFailed(match_id: int, user_id: int) -> None:
    """
    Send userID's failed packet to everyone in match

    :param userID: ID of user
    :return:
    """
    # Make sure the user is in room
    slot_id = getUserSlotID(match_id, user_id)
    if slot_id is None:
        return

    _slot = slot.get_slot(match_id, slot_id)
    assert _slot is not None

    _slot = slot.update_slot(match_id, slot_id, passed=False)

    # Send packet to all players
    playing_stream_name = create_playing_stream_name(match_id)
    streamList.broadcast(
        playing_stream_name,
        serverPackets.playerFailed(slot_id),
    )

def invite(match_id: int, fro: int, to: int) -> None:
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
            glob.BOT_NAME,
            froToken.username,
            "I'd love to join your match, but I've got a job to do!.",
        )
        return

    multiplayer_match = get_match(match_id)
    assert multiplayer_match is not None

    # Send message
    pw_safe = multiplayer_match['match_password'].replace(" ", "_")
    message = (
        "Come join my multiplayer match: "
        f'"[osump://{multiplayer_match["match_id"]}/{pw_safe} {multiplayer_match["match_name"]}]"'
    )
    chat.sendMessage(token=froToken, to=toToken.username, message=message)

def countUsers(match_id: int) -> int:
    """
    Return how many players are in that match

    :return: number of users
    """
    slots = slot.get_slots(match_id)
    assert len(slots) == 16

    return sum(1 for slot in slots if slot["user_token"] is not None)

def changeTeam(match_id: int, user_id: int, new_team: Optional[int] = None) -> None:
    """
    Change userID's team

    :param userID: id of user
    :return:
    """
    multiplayer_match = get_match(match_id)
    assert multiplayer_match is not None

    # Make sure this match's mode has teams
    if (
        multiplayer_match["match_team_type"] != matchTeamTypes.TEAM_VS
        and multiplayer_match["match_team_type"] != matchTeamTypes.TAG_TEAM_VS
    ):
        return

    # Make sure the match is not locked
    if multiplayer_match["is_locked"] or multiplayer_match["is_starting"]:
        return

    # Make sure the user is in room
    slot_id = getUserSlotID(match_id, user_id)
    if slot_id is None:
        return

    slots = slot.get_slots(match_id)
    assert len(slots) == 16

    # Update slot and send update
    if new_team is None:
        if slots[slot_id]["team"] == matchTeams.RED:
            new_team = matchTeams.BLUE
        else:
            new_team = matchTeams.RED

        setSlot(match_id, slot_id, status=None, team=new_team)

    sendUpdates(match_id)

def sendUpdates(match_id: int) -> None:
    """
    Send match updates packet to everyone in lobby and room streams

    :return:
    """
    uncensored_data = serverPackets.updateMatch(match_id)
    if uncensored_data is not None:
        stream_name = create_stream_name(match_id)
        streamList.broadcast(stream_name, uncensored_data)

    censored_data = serverPackets.updateMatch(match_id, censored=True)
    if censored_data is not None:
        streamList.broadcast("lobby", censored_data)
    else:
        log.error(
            f"MPROOM{match_id}: Can't send match update packet, match data is None!!!",
        )

def checkTeams(match_id: int) -> bool:
    """
    Check if match teams are valid

    :return: True if valid, False if invalid
    :return:
    """
    multiplayer_match = get_match(match_id)
    assert multiplayer_match is not None

    if (
        multiplayer_match["match_team_type"] != matchTeamTypes.TEAM_VS
        and multiplayer_match["match_team_type"] != matchTeamTypes.TAG_TEAM_VS
    ):
        # Teams are always valid if we have no teams
        return True

    # We have teams, check if they are valid
    firstTeam = -1

    slots = slot.get_slots(match_id)
    assert len(slots) == 16

    for _slot in slots:
        if _slot["user_token"] and (_slot["status"] & slotStatuses.NO_MAP) == 0:
            if firstTeam == -1:
                firstTeam = _slot["team"]
            elif firstTeam != _slot["team"]:
                return True

    log.warning(f"MPROOM{match_id}: Invalid teams!")
    return False

def start(match_id: int) -> bool:
    """
    Start the match

    :return:
    """
    multiplayer_match = get_match(match_id)
    assert multiplayer_match is not None

    # Remove isStarting timer flag thingie
    multiplayer_match = update_match(match_id, is_starting=False)
    assert multiplayer_match is not None

    # Make sure we have enough players
    if not checkTeams(match_id):
        return False

    # Create playing channel
    playing_stream_name = create_playing_stream_name(match_id)
    streamList.add(playing_stream_name)

    # Change inProgress value
    multiplayer_match = update_match(match_id, is_in_progress=True)
    assert multiplayer_match is not None

    # Set playing to ready players and set load, skip and complete to False
    # Make clients join playing stream
    slots = slot.get_slots(match_id)
    assert len(slots) == 16

    for _slot in slots:
        if _slot["user_token"] is None:
            continue

        if _slot["user_token"] in glob.tokens.tokens:
            _slot["status"] = slotStatuses.PLAYING
            _slot["loaded"] = False
            _slot["skip"] = False
            _slot["complete"] = False

            user_token = glob.tokens.tokens[_slot["user_token"]]
            user_token.joinStream(playing_stream_name)

    # Send match start packet
    streamList.broadcast(
        playing_stream_name,
        serverPackets.matchStart(match_id),
    )

    # Send updates
    sendUpdates(match_id)
    return True

def forceSize(match_id: int, matchSize: int) -> None:
    slots = slot.get_slots(match_id)
    assert len(slots) == 16

    for i in range(matchSize):
        if slots[i]["status"] == slotStatuses.LOCKED:
            toggleSlotLocked(match_id, i)
    for i in range(matchSize, 16):
        if slots[i]["status"] != slotStatuses.LOCKED:
            toggleSlotLocked(match_id, i)

def abort(match_id: int) -> None:
    multiplayer_match = get_match(match_id)
    assert multiplayer_match is not None

    if not multiplayer_match["is_in_progress"]:
        log.warning(f"MPROOM{match_id}: Match is not in progress!")
        return

    multiplayer_match = update_match(match_id, is_in_progress=False, is_starting=False)
    assert multiplayer_match is not None

    resetSlots(match_id)
    sendUpdates(match_id)

    playing_stream_name = create_playing_stream_name(match_id)
    streamList.broadcast(playing_stream_name, serverPackets.matchAbort)
    streamList.dispose(playing_stream_name)
    streamList.remove(playing_stream_name)

def initializeTeams(match_id: int) -> None:
    multiplayer_match = get_match(match_id)
    assert multiplayer_match is not None

    slots = slot.get_slots(match_id)
    assert len(slots) == 16

    if multiplayer_match["match_team_type"] in {matchTeamTypes.TEAM_VS, matchTeamTypes.TAG_TEAM_VS}:
        # Set teams
        for slot_id in range(len(slots)):
            new_team = matchTeams.RED if slot_id % 2 == 0 else matchTeams.BLUE
            slot.update_slot(match_id, slot_id, team=new_team)
    else:
        # Reset teams
        for slot_id in range(len(slots)):
            new_team = matchTeams.NO_TEAM
            slot.update_slot(match_id, slot_id, team=new_team)

def resetMods(match_id: int) -> None:
    slots = slot.get_slots(match_id)
    assert len(slots) == 16

    for slot_id in range(len(slots)):
        slot.update_slot(match_id, slot_id, mods=0)

def resetReady(match_id: int) -> None:
    slots = slot.get_slots(match_id)
    assert len(slots) == 16

    for slot_id, _slot in enumerate(slots):
        if _slot["status"] == slotStatuses.READY:
            new_status = slotStatuses.NOT_READY
            slot.update_slot(match_id, slot_id, status=new_status)

def sendReadyStatus(match_id: int) -> None:
    channel_name = f"#multi_{match_id}"

    # Make sure match exists before attempting to do anything else
    if channel_name not in channelList.getChannelNames():
        return

    slots = slot.get_slots(match_id)
    assert len(slots) == 16

    totalUsers = 0
    readyUsers = 0

    for _slot in slots:
        # Make sure there is a user in this slot
        if _slot["user_token"] is None:
            continue

        # In this slot there is a user, so we increase the amount of total users
        # in this multi room.
        totalUsers += 1

        if _slot["status"] == slotStatuses.READY:
            readyUsers += 1

    if totalUsers == 0:
        message = "The match is now empty."
    else:
        message = [f"{readyUsers} users ready out of {totalUsers}."]
        if totalUsers == readyUsers:
            message.append("All users ready!")

        message = " ".join(message)

    chat.sendMessage(glob.BOT_NAME, channel_name, message)

# TODO: abstract these redis calls into a repository

def add_referee(match_id: int, user_id: int) -> None:
    multiplayer_match = get_match(match_id)
    assert multiplayer_match is not None

    glob.redis.sadd(f"bancho:matches:{match_id}:referees", user_id)

def get_referees(match_id: int) -> set[int]:
    multiplayer_match = get_match(match_id)
    assert multiplayer_match is not None

    raw_referees: set[bytes] = glob.redis.smembers(f"bancho:matches:{match_id}:referees")
    referees = {int(referee) for referee in raw_referees}

    return referees

def remove_referee(match_id: int, user_id: int) -> None:
    multiplayer_match = get_match(match_id)
    assert multiplayer_match is not None

    glob.redis.srem(f"bancho:matches:{match_id}:referees", user_id)
