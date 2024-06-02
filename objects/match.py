from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any
from typing import TypedDict
from typing import cast

import orjson

from common.log import logger
from constants import CHATBOT_USER_ID
from constants import dataTypes
from constants import matchModModes
from constants import matchTeams
from constants import matchTeamTypes
from constants import serverPackets
from constants import slotStatuses
from constants.match_events import MatchEvents
from helpers import chatHelper as chat
from helpers.scoreHelper import calculate_accuracy
from objects import channelList
from objects import glob
from objects import match
from objects import matchList
from objects import osuToken
from objects import slot
from objects import streamList
from objects import tokenList

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
    match_scoring_type: int  # matchScoringTypes
    match_team_type: int  # matchTeamTypes
    match_mod_mode: int  # matchModModes
    seed: int
    is_tourney: bool
    is_locked: bool
    is_starting: bool
    is_timer_running: bool
    is_in_progress: bool
    creation_time: float

    match_history_private: bool
    current_game_id: int

    # now separate
    # slots: list[slot.Slot]
    # referees: set[int]


def make_key(match_id: int) -> str:
    return f"bancho:matches:{match_id}"


def make_lock_key(match_id: int) -> str:
    return f"bancho:matches:{match_id}:lock"


async def create_match(
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
    is_timer_running: bool,
    is_in_progress: bool,
    creation_time: float,
    current_game_id: int,
) -> Match:
    match_history_private = False
    if match_password.endswith("//private"):
        match_password = match_password.rstrip("//private")
        match_history_private = True

    match_id = await insert_match(match_name, match_history_private)
    await insert_match_event(match_id, MatchEvents.MATCH_CREATION, user_id=host_user_id)

    await glob.redis.sadd("bancho:matches", match_id)
    for slot_id in range(16):
        await slot.create_slot(match_id, slot_id)
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
        "is_timer_running": is_timer_running,
        "is_in_progress": is_in_progress,
        "creation_time": creation_time,
        "match_history_private": match_history_private,
        "current_game_id": current_game_id,
    }
    await glob.redis.set(make_key(match_id), orjson.dumps(match))
    return match


async def get_match_ids() -> set[int]:
    raw_match_ids = await glob.redis.smembers("bancho:matches")
    return {int(match_id) for match_id in raw_match_ids}


async def get_match(match_id: int) -> Match | None:
    raw_match = await glob.redis.get(make_key(match_id))
    if raw_match is None:
        return None

    return cast(Match, orjson.loads(raw_match))


async def update_match(
    match_id: int,
    *,
    match_name: str | None = None,
    match_password: str | None = None,
    beatmap_id: int | None = None,
    beatmap_name: str | None = None,
    beatmap_md5: str | None = None,
    game_mode: int | None = None,
    host_user_id: int | None = None,
    mods: int | None = None,
    match_scoring_type: int | None = None,
    match_team_type: int | None = None,
    match_mod_mode: int | None = None,
    seed: int | None = None,
    is_tourney: bool | None = None,
    is_locked: bool | None = None,
    is_starting: bool | None = None,
    is_timer_running: bool | None = None,
    is_in_progress: bool | None = None,
    creation_time: float | None = None,
    game_id: int | None = None,
) -> Match | None:
    match = await get_match(match_id)
    if match is None:
        return None

    if match_name is not None and match["match_name"] != match_name:
        await update_match_name(match_id, match_name)

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
    if is_timer_running is not None:
        match["is_timer_running"] = is_timer_running
    if is_in_progress is not None:
        match["is_in_progress"] = is_in_progress
    if creation_time is not None:
        match["creation_time"] = creation_time
    if game_id is not None:
        match["current_game_id"] = game_id

    await glob.redis.set(make_key(match_id), orjson.dumps(match))
    return match


async def delete_match(match_id: int) -> None:
    # TODO: should we throw error when no match exists?
    async with glob.redis.pipeline() as pipe:
        await pipe.srem("bancho:matches", match_id)
        await pipe.delete(make_key(match_id))
        await pipe.execute()

    # TODO: should devs have to do this separately?
    await slot.delete_slots(match_id)


def create_stream_name(match_id: int) -> str:
    return f"multi/{match_id}"


def create_playing_stream_name(match_id: int) -> str:
    return f"multi/{match_id}/playing"


async def getMatchData(
    match_id: int,
    censored: bool = False,
) -> tuple[tuple[object, int], ...]:
    """
    Return binary match data structure for packetHelper

    :param match_id: Match ID
    :param censored: Whether to censor password
    :return:
    """
    # General match info

    multiplayer_match = await get_match(match_id)
    assert multiplayer_match is not None

    slots = await slot.get_slots(match_id)
    assert len(slots) == 16

    struct: list[tuple[object, int]] = [
        (multiplayer_match["match_id"], dataTypes.UINT16),
        (int(multiplayer_match["is_in_progress"]), dataTypes.BYTE),
        (0, dataTypes.BYTE),  # TODO: what is this?
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
            (await tokenList.getUserIDFromToken(slot["user_token"]), dataTypes.UINT32)
            for slot in slots
            if (
                slot["user_token"]
                and await osuToken.get_token(slot["user_token"]) is not None
            )
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


async def setHost(match_id: int, new_host_id: int) -> bool:
    """
    Set room host to newHost and send him host packet

    :param match_id: match id
    :param newHost: new host userID
    :return:
    """

    multiplayer_match = await get_match(match_id)
    assert multiplayer_match is not None

    if multiplayer_match["host_user_id"] != -1:
        old_host = await osuToken.get_token_by_user_id(
            multiplayer_match["host_user_id"],
        )
        assert old_host is not None

        if not osuToken.is_staff(old_host["privileges"]):
            await remove_referee(match_id, multiplayer_match["host_user_id"])

    await add_referee(match_id, new_host_id)

    slot_id = await getUserSlotID(match_id, new_host_id)
    if slot_id is None:
        return False

    _slot = await slot.get_slot(match_id, slot_id)
    assert _slot is not None

    if _slot["user_token"] is None:
        return False

    user_token = await osuToken.get_token(_slot["user_token"])
    if user_token is None:
        return False

    await match.update_match(
        match_id,
        host_user_id=new_host_id,
    )

    await insert_match_event(
        match_id,
        MatchEvents.MATCH_HOST_ASSIGNMENT,
        user_id=new_host_id,
    )
    await osuToken.enqueue(user_token["token_id"], serverPackets.matchTransferHost)
    await sendUpdates(match_id)
    return True


def get_match_history_url(match_id: int) -> str:
    return f"https://akatsuki.gg/matches/{match_id}"


def get_match_history_message(match_id: int, is_history_private: bool) -> str:
    mp_history_link = get_match_history_url(match_id)

    message = f"Match history available [{mp_history_link} here]."
    if is_history_private:
        message += " This is only visible to participants of this match!"

    return message


async def removeHost(match_id: int, rm_referee: bool = True) -> None:
    """
    Removes the host (for tourney matches)

    :param match_id: match id
    :return:
    """

    multiplayer_match = await get_match(match_id)
    assert multiplayer_match is not None

    if rm_referee:
        await remove_referee(match_id, multiplayer_match["host_user_id"])

    await update_match(match_id, host_user_id=-1)

    await sendUpdates(match_id)


# TODO: this func probably should not exist; jkurwa
async def setSlot(
    match_id: int,
    slot_id: int,
    status: int | None = None,
    team: int | None = None,
    user_id: int | None = None,
    user_token: str | None = "",  # TODO: need to refactor stuff for this
    mods: int | None = None,
    loaded: bool | None = None,
    skip: bool | None = None,
    complete: bool | None = None,
) -> slot.Slot:
    _slot = await slot.get_slot(match_id, slot_id)
    assert _slot is not None

    _slot = await slot.update_slot(
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


async def setSlotMods(match_id: int, slot_id: int, mods: int) -> None:
    """
    Set slotID mods. Same as calling setSlot and then sendUpdate

    :param slotID: slot number
    :param mods: new mods
    :return:
    """
    # Set new slot data and send update
    await setSlot(match_id, slot_id, mods=mods)
    await sendUpdates(match_id)


async def toggleSlotReady(match_id: int, slot_id: int) -> None:
    """
    Switch slotID ready/not ready status
    Same as calling setSlot and then sendUpdate

    :param slotID: slot number
    :return:
    """

    multiplayer_match = await get_match(match_id)
    assert multiplayer_match is not None

    _slot = await slot.get_slot(match_id, slot_id)
    assert _slot is not None

    # Update ready status and setnd update
    if not _slot["user_token"] or multiplayer_match["is_starting"]:
        return

    oldStatus = _slot["status"]
    if oldStatus == slotStatuses.READY:
        newStatus = slotStatuses.NOT_READY
    else:
        newStatus = slotStatuses.READY

    await setSlot(match_id, slot_id, newStatus)
    await sendUpdates(match_id)


async def toggleSlotLocked(match_id: int, slot_id: int) -> None:
    """
    Lock a slot
    Same as calling setSlot and then sendUpdate

    :param slotID: slot number
    :return:
    """

    _slot = await slot.get_slot(match_id, slot_id)
    assert _slot is not None

    # Check if slot is already locked
    if _slot["status"] == slotStatuses.LOCKED:
        newStatus = slotStatuses.FREE
    else:
        newStatus = slotStatuses.LOCKED

    # Send updated settings to kicked user, so he returns to lobby
    if _slot["user_token"] and _slot["user_token"] in await osuToken.get_token_ids():
        packet_data = await serverPackets.updateMatch(match_id)
        if packet_data is None:
            # TODO: is this correct behaviour?
            # ripple was doing this before the stateless refactor,
            # but i'm pretty certain the osu! client won't like this.
            await osuToken.enqueue(_slot["user_token"], b"")
            return None

        await osuToken.enqueue(_slot["user_token"], packet_data)

    # Set new slot status
    await setSlot(
        match_id,
        slot_id=slot_id,
        status=newStatus,
        team=0,
        user_token=None,
        mods=0,
        user_id=-1,
    )

    # Send updates to everyone else
    await sendUpdates(match_id)


async def playerLoaded(match_id: int, user_id: int) -> None:
    """
    Set a player loaded status to True

    :param userID: ID of user
    :return:
    """
    slot_id = await getUserSlotID(match_id, user_id)
    if slot_id is None:
        return

    # Set loaded to True
    _slot = await slot.get_slot(match_id, slot_id)
    assert _slot is not None

    _slot = await slot.update_slot(match_id, slot_id, loaded=True)
    assert _slot is not None

    slots = await slot.get_slots(match_id)
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
        await allPlayersLoaded(match_id)


async def allPlayersLoaded(match_id: int) -> None:
    """
    Send allPlayersLoaded packet to every playing usr in match

    :return:
    """
    multiplayer_match = await get_match(match_id)
    assert multiplayer_match is not None

    playing_stream_name = create_playing_stream_name(match_id)
    await streamList.broadcast(playing_stream_name, serverPackets.allPlayersLoaded)


async def playerSkip(match_id: int, user_id: int) -> None:
    """
    Set a player skip status to True

    :param userID: ID of user
    :return:
    """
    slot_id = await getUserSlotID(match_id, user_id)
    if slot_id is None:
        return

    _slot = await slot.get_slot(match_id, slot_id)
    assert _slot is not None

    # Set skip to True
    _slot = await slot.update_slot(match_id, slot_id, skip=True)
    assert _slot is not None

    # Send skip packet to every playing user
    playing_stream_name = create_playing_stream_name(match_id)
    packet_data = serverPackets.playerSkipped(slot_id)
    await streamList.broadcast(playing_stream_name, packet_data)

    slots = await slot.get_slots(match_id)
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
        await allPlayersSkipped(match_id)


async def allPlayersSkipped(match_id: int) -> None:
    """
    Send allPlayersSkipped packet to every playing usr in match

    :return:
    """

    playing_stream_name = create_playing_stream_name(match_id)
    await streamList.broadcast(playing_stream_name, serverPackets.allPlayersSkipped)


async def playerCompleted(match_id: int, user_id: int) -> None:
    """
    Set userID's slot completed to True

    :param userID: ID of user
    """
    slot_id = await getUserSlotID(match_id, user_id)
    if slot_id is None:
        return

    await setSlot(match_id, slot_id, complete=True)

    slots = await slot.get_slots(match_id)
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
        await allPlayersCompleted(match_id)


async def allPlayersCompleted(match_id: int) -> None:
    """
    Cleanup match stuff and send match end packet to everyone

    :return:
    """
    multiplayer_match = await get_match(match_id)
    assert multiplayer_match is not None

    slots = await slot.get_slots(match_id)
    assert len(slots) == 16

    # Reset inProgress
    multiplayer_match = await update_match(match_id, is_in_progress=False)
    assert multiplayer_match is not None

    # Reset slots
    await resetSlots(match_id)

    # Send match update
    await sendUpdates(match_id)

    # Send match complete
    stream_name = create_stream_name(match_id)
    await streamList.broadcast(stream_name, serverPackets.matchComplete)

    # Destroy playing stream
    playing_stream_name = create_playing_stream_name(match_id)
    await streamList.dispose(playing_stream_name)

    if multiplayer_match["current_game_id"] != 0:
        await finish_match_game(multiplayer_match["current_game_id"])

    # Console output
    # log.info("MPROOM{}: Match completed".format(self.matchID))

    channel_name = f"#mp_{match_id}"

    # If this is a tournament match, then we send a notification in the chat
    # saying that the match has completed.
    if (
        multiplayer_match["is_tourney"]
        and channel_name in await channelList.getChannelNames()
    ):
        chatbot_token = await osuToken.get_token_by_user_id(CHATBOT_USER_ID)
        assert chatbot_token is not None
        await chat.send_message(
            sender_token_id=chatbot_token["token_id"],
            recipient_name=channel_name,
            message="Match has just finished.",
        )


async def resetSlots(match_id: int) -> None:
    slots = await slot.get_slots(match_id)
    assert len(slots) == 16

    # TODO: make sure slot_id is right?
    # not sure about the order.
    # also not sure we start from 0.
    for slot_id, _slot in enumerate(slots):
        if _slot["user_token"] is not None and _slot["status"] == slotStatuses.PLAYING:
            await slot.update_slot(
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


async def getUserSlotID(match_id: int, user_id: int) -> int | None:
    """
    Get slot ID occupied by userID

    :return: slot id if found, None if user is not in room
    """
    slots = await slot.get_slots(match_id)
    assert len(slots) == 16

    for slot_id, _slot in enumerate(slots):
        if _slot["user_id"] == user_id:
            return slot_id

    return None


async def userJoin(match_id: int, token_id: str) -> bool:
    """
    Add someone to users in match

    :param user: user object of the user
    :return: True if join success, False if fail (room is full)
    """
    multiplayer_match = await get_match(match_id)
    assert multiplayer_match is not None

    slots = await slot.get_slots(match_id)
    assert len(slots) == 16

    token = await osuToken.get_token(token_id)
    assert token is not None

    # Make sure we're not in this match
    for slot_id, _slot in enumerate(slots):
        if _slot["user_token"] == token_id:
            # Set bugged slot to free
            await setSlot(
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

            await setSlot(
                match_id,
                slot_id,
                status=slotStatuses.NOT_READY,
                team=team,
                user_token=token_id,
                mods=0,
                user_id=token["user_id"],
            )

            if osuToken.is_staff(token["privileges"]):
                await add_referee(match_id, token["user_id"])

            await insert_match_event(
                match_id,
                MatchEvents.MATCH_USER_JOIN,
                user_id=token["user_id"],
            )

            # Send updated match data
            await sendUpdates(match_id)
            return True

    if osuToken.is_staff(
        token["privileges"],
    ):  # Allow mods+ to join into locked but empty slots.
        for slot_id, _slot in enumerate(slots):
            if _slot["status"] == slotStatuses.LOCKED and _slot["user_id"] == -1:
                if multiplayer_match["match_team_type"] in (
                    matchTeamTypes.TEAM_VS,
                    matchTeamTypes.TAG_TEAM_VS,
                ):
                    team = matchTeams.RED if slot_id % 2 == 0 else matchTeams.BLUE
                else:
                    team = matchTeams.NO_TEAM

                await setSlot(
                    match_id,
                    slot_id,
                    status=slotStatuses.NOT_READY,
                    team=team,
                    user_token=token["token_id"],
                    mods=0,
                    user_id=token["user_id"],
                )

                await insert_match_event(
                    match_id,
                    MatchEvents.MATCH_USER_JOIN,
                    user_id=token["user_id"],
                )

                # Send updated match data
                await sendUpdates(match_id)
                return True

    return False


async def userLeft(match_id: int, token_id: str, disposeMatch: bool = True) -> None:
    """
    Remove someone from users in match

    :param user: user object of the user
    :param disposeMatch: if `True`, will try to dispose match if there are no users in the room
    :return:
    """
    multiplayer_match = await get_match(match_id)
    assert multiplayer_match is not None

    token = await osuToken.get_token(token_id)
    assert token is not None

    # Make sure the user is in room
    slot_id = await getUserSlotID(match_id, token["user_id"])
    if slot_id is None:
        return

    # Set that slot to free
    await setSlot(
        match_id,
        slot_id,
        status=slotStatuses.FREE,
        team=0,
        user_token=None,
        mods=0,
        user_id=-1,
    )

    await osuToken.update_token(
        token_id,
        match_id=None,
    )

    await insert_match_event(
        match_id,
        MatchEvents.MATCH_USER_LEFT,
        user_id=token["user_id"],
    )

    # Check if everyone left
    if (
        await countUsers(match_id) == 0
        and disposeMatch
        and not multiplayer_match["is_tourney"]
    ):
        # Dispose match
        await insert_match_event(
            match_id,
            MatchEvents.MATCH_DISBAND,
        )
        await finish_match(match_id)
        await matchList.disposeMatch(multiplayer_match["match_id"])  # TODO
        # log.info("MPROOM{}: Room disposed because all users left.".format(self.matchID))
        return

    slots = await slot.get_slots(match_id)
    assert len(slots) == 16

    # Check if host left
    if token["user_id"] == multiplayer_match["host_user_id"]:
        # Give host to someone else
        for _slot in slots:
            if _slot["user_token"] is None:
                continue

            token = await osuToken.get_token(_slot["user_token"])
            if token is None:
                continue

            await setHost(match_id, token["user_id"])
            break

    # Send updated match data
    await sendUpdates(match_id)


async def userChangeSlot(match_id: int, user_id: int, new_slot_id: int) -> bool:
    """
    Change userID slot to newSlotID

    :param userID: user that changed slot
    :param newSlotID: slot id of new slot
    :return:
    """

    multiplayer_match = await get_match(match_id)
    assert multiplayer_match is not None

    slots = await slot.get_slots(match_id)
    assert len(slots) == 16

    # Make sure the match is not locked
    if multiplayer_match["is_locked"] or multiplayer_match["is_starting"]:
        return False

    # Make sure the user is in room
    old_slot_id = await getUserSlotID(match_id, user_id)
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
    old_data = deepcopy(slots[old_slot_id])

    # Free old slot
    await setSlot(
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
    await setSlot(
        match_id,
        new_slot_id,
        status=old_data["status"],
        team=old_data["team"],
        user_token=old_data["user_token"],
        mods=old_data["mods"],
        user_id=old_data["user_id"],
    )

    # Send updated match data
    await sendUpdates(match_id)

    return True


async def changePassword(match_id: int, newPassword: str) -> None:
    """
    Change match password to newPassword

    :param newPassword: new password string
    :return:
    """
    multiplayer_match = await get_match(match_id)
    assert multiplayer_match is not None

    multiplayer_match = await update_match(match_id, match_password=newPassword)
    assert multiplayer_match is not None

    # Send password change to every user in match
    await streamList.broadcast(
        create_stream_name(match_id),
        serverPackets.changeMatchPassword(multiplayer_match["match_password"]),
    )

    # Send new match settings too
    await sendUpdates(match_id)


async def changeMods(match_id: int, mods: int) -> None:
    """
    Set match global mods

    :param mods: mods bitwise int thing
    :return:
    """
    multiplayer_match = await get_match(match_id)
    assert multiplayer_match is not None

    # Set new mods and send update
    multiplayer_match = await update_match(match_id, mods=mods)
    assert multiplayer_match is not None

    await sendUpdates(match_id)


async def userHasBeatmap(match_id: int, user_id: int, has_beatmap: bool = True) -> None:
    """
    Set no beatmap status for userID

    :param userID: ID of user
    :param has: True if has beatmap, false if not
    :return:
    """
    # Make sure the user is in room
    slot_id = await getUserSlotID(match_id, user_id)
    if slot_id is None:
        return

    # Set slot
    if has_beatmap:
        new_status = slotStatuses.NOT_READY
    else:
        new_status = slotStatuses.NO_MAP

    await setSlot(match_id, slot_id, new_status)

    # Send updates
    await sendUpdates(match_id)


async def transferHost(match_id: int, slot_id: int) -> None:
    """
    Transfer host to slotID

    :param slotID: ID of slot
    :return:
    """
    _slot = await slot.get_slot(match_id, slot_id)
    assert _slot is not None

    # Make sure there is someone in that slot
    if (
        not _slot["user_token"]
        or _slot["user_token"] not in await osuToken.get_token_ids()
    ):
        return

    # Transfer host
    await setHost(match_id, _slot["user_id"])


async def playerFailed(match_id: int, user_id: int) -> None:
    """
    Send userID's failed packet to everyone in match

    :param userID: ID of user
    :return:
    """
    # Make sure the user is in room
    slot_id = await getUserSlotID(match_id, user_id)
    if slot_id is None:
        return

    _slot = await slot.get_slot(match_id, slot_id)
    assert _slot is not None

    _slot = await slot.update_slot(match_id, slot_id, passed=False)

    # Send packet to all players
    playing_stream_name = create_playing_stream_name(match_id)
    await streamList.broadcast(
        playing_stream_name,
        serverPackets.playerFailed(slot_id),
    )


async def invite(match_id: int, sender_user_id: int, recipient_user_id: int) -> None:
    """One user currently in a match, invites another user to the match."""
    # Get tokens
    froToken = await osuToken.get_token_by_user_id(sender_user_id)
    toToken = await osuToken.get_token_by_user_id(recipient_user_id)
    if not froToken or not toToken:
        return

    # Aika is too busy
    if recipient_user_id == CHATBOT_USER_ID:
        await chat.send_message(
            sender_token_id=toToken["token_id"],
            recipient_name=froToken["username"],
            message="I'd love to join your match, but I've got a job to do!.",
        )
        return

    multiplayer_match = await get_match(match_id)
    assert multiplayer_match is not None

    # Send message
    pw_safe = multiplayer_match["match_password"].replace(" ", "_")
    message = (
        "Come join my multiplayer match: "
        f'"[osump://{multiplayer_match["match_id"]}/{pw_safe} {multiplayer_match["match_name"]}]"'
    )
    await chat.send_message(
        sender_token_id=froToken["token_id"],
        recipient_name=toToken["username"],
        message=message,
    )


async def countUsers(match_id: int) -> int:
    """
    Return how many players are in that match

    :return: number of users
    """
    slots = await slot.get_slots(match_id)
    assert len(slots) == 16

    return sum(1 for slot in slots if slot["user_token"] is not None)


async def changeTeam(
    match_id: int,
    user_id: int,
    new_team: int | None = None,
) -> None:
    """
    Change userID's team

    :param userID: id of user
    :return:
    """
    multiplayer_match = await get_match(match_id)
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
    slot_id = await getUserSlotID(match_id, user_id)
    if slot_id is None:
        return

    slots = await slot.get_slots(match_id)
    assert len(slots) == 16

    # Update slot and send update
    if new_team is None:
        if slots[slot_id]["team"] == matchTeams.RED:
            new_team = matchTeams.BLUE
        else:
            new_team = matchTeams.RED

    await setSlot(match_id, slot_id, status=None, team=new_team)
    await sendUpdates(match_id)


async def sendUpdates(match_id: int) -> None:
    """
    Send match updates packet to everyone in lobby and room streams

    :return:
    """
    uncensored_data = await serverPackets.updateMatch(match_id)
    if uncensored_data is not None:
        stream_name = create_stream_name(match_id)
        await streamList.broadcast(stream_name, uncensored_data)

    censored_data = await serverPackets.updateMatch(match_id, censored=True)
    if censored_data is not None:
        await streamList.broadcast("lobby", censored_data)
    else:
        logger.error(
            f"Failed to send updates to a multiplayer match",
            extra={"match_id": match_id},
        )


async def checkTeams(match_id: int) -> bool:
    """
    Check if match teams are valid

    :return: True if valid, False if invalid
    :return:
    """
    multiplayer_match = await get_match(match_id)
    assert multiplayer_match is not None

    if (
        multiplayer_match["match_team_type"] != matchTeamTypes.TEAM_VS
        and multiplayer_match["match_team_type"] != matchTeamTypes.TAG_TEAM_VS
    ):
        # Teams are always valid if we have no teams
        return True

    # We have teams, check if they are valid
    firstTeam = -1

    slots = await slot.get_slots(match_id)
    assert len(slots) == 16

    for _slot in slots:
        if _slot["user_token"] and (_slot["status"] & slotStatuses.NO_MAP) == 0:
            if firstTeam == -1:
                firstTeam = _slot["team"]
            elif firstTeam != _slot["team"]:
                return True

    logger.warning(
        "Invalid teams detected for multiplayer match",
        extra={"match_id": match_id},
    )
    return False


async def start(match_id: int) -> bool:
    """
    Start the match

    :return:
    """
    multiplayer_match = await get_match(match_id)
    assert multiplayer_match is not None

    # Reset game id
    multiplayer_match = await update_match(match_id, game_id=0)
    assert multiplayer_match is not None

    # Remove isStarting timer flag thingie
    multiplayer_match = await update_match(match_id, is_starting=False)
    assert multiplayer_match is not None

    # Make sure we have enough players
    if not await checkTeams(match_id):
        return False

    # Create playing channel
    playing_stream_name = create_playing_stream_name(match_id)
    await streamList.add(playing_stream_name)

    # Change inProgress value
    multiplayer_match = await update_match(match_id, is_in_progress=True)
    assert multiplayer_match is not None

    # Set playing to ready players and set load, skip and complete to False
    # Make clients join playing stream
    slots = await slot.get_slots(match_id)
    assert len(slots) == 16

    for slot_id, _slot in enumerate(slots):
        if _slot["user_token"] is None:
            continue

        user_token = await osuToken.get_token(_slot["user_token"])
        if user_token is not None:
            await slot.update_slot(
                match_id,
                slot_id,
                status=slotStatuses.PLAYING,
                loaded=False,
                skip=False,
                complete=False,
            )

            await osuToken.joinStream(user_token["token_id"], playing_stream_name)

    # Send match start packet
    await streamList.broadcast(
        playing_stream_name,
        await serverPackets.matchStart(match_id),
    )

    game_id = await insert_match_game(
        match_id,
        multiplayer_match["beatmap_id"],
        multiplayer_match["game_mode"],
        multiplayer_match["mods"],
        multiplayer_match["match_scoring_type"],
        multiplayer_match["match_team_type"],
    )
    multiplayer_match = await update_match(match_id, game_id=game_id)
    assert multiplayer_match is not None

    # Send updates
    await sendUpdates(match_id)
    await insert_match_event(
        match_id,
        MatchEvents.MATCH_GAME_PLAYTHROUGH,
        game_id=game_id,
    )
    return True


async def forceSize(match_id: int, matchSize: int) -> None:
    slots = await slot.get_slots(match_id)
    assert len(slots) == 16

    for i in range(matchSize):
        if slots[i]["status"] == slotStatuses.LOCKED:
            await toggleSlotLocked(match_id, i)
    for i in range(matchSize, 16):
        if slots[i]["status"] != slotStatuses.LOCKED:
            await toggleSlotLocked(match_id, i)


async def abort(match_id: int) -> None:
    multiplayer_match = await get_match(match_id)
    assert multiplayer_match is not None

    if not multiplayer_match["is_in_progress"]:
        return

    multiplayer_match = await update_match(
        match_id,
        is_in_progress=False,
        is_starting=False,
    )
    assert multiplayer_match is not None

    await resetSlots(match_id)
    await sendUpdates(match_id)

    playing_stream_name = create_playing_stream_name(match_id)
    await streamList.broadcast(playing_stream_name, serverPackets.matchAbort)
    await streamList.dispose(playing_stream_name)


async def initializeTeams(match_id: int) -> None:
    multiplayer_match = await get_match(match_id)
    assert multiplayer_match is not None

    slots = await slot.get_slots(match_id)
    assert len(slots) == 16

    if multiplayer_match["match_team_type"] in {
        matchTeamTypes.TEAM_VS,
        matchTeamTypes.TAG_TEAM_VS,
    }:
        # Set teams
        for slot_id in range(len(slots)):
            new_team = matchTeams.RED if slot_id % 2 == 0 else matchTeams.BLUE
            await slot.update_slot(match_id, slot_id, team=new_team)
    else:
        # Reset teams
        for slot_id in range(len(slots)):
            new_team = matchTeams.NO_TEAM
            await slot.update_slot(match_id, slot_id, team=new_team)


async def resetMods(match_id: int) -> None:
    slots = await slot.get_slots(match_id)
    assert len(slots) == 16

    for slot_id in range(len(slots)):
        await slot.update_slot(match_id, slot_id, mods=0)


async def resetReady(match_id: int) -> None:
    slots = await slot.get_slots(match_id)
    assert len(slots) == 16

    for slot_id, _slot in enumerate(slots):
        if _slot["status"] == slotStatuses.READY:
            new_status = slotStatuses.NOT_READY
            await slot.update_slot(match_id, slot_id, status=new_status)


async def sendReadyStatus(match_id: int) -> None:
    channel_name = f"#mp_{match_id}"

    # Make sure match exists before attempting to do anything else
    if channel_name not in await channelList.getChannelNames():
        return

    slots = await slot.get_slots(match_id)
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
        message = f"{readyUsers} users ready out of {totalUsers}."
        if totalUsers == readyUsers:
            message += " All users ready!"

    chatbot_token = await osuToken.get_token_by_user_id(CHATBOT_USER_ID)
    assert chatbot_token is not None
    await chat.send_message(
        sender_token_id=chatbot_token["token_id"],
        recipient_name=channel_name,
        message=message,
    )


# TODO: abstract these redis calls into a repository


async def add_referee(match_id: int, user_id: int) -> None:
    multiplayer_match = await get_match(match_id)
    assert multiplayer_match is not None

    await glob.redis.sadd(f"bancho:matches:{match_id}:referees", user_id)


async def get_referees(match_id: int) -> set[int]:
    multiplayer_match = await get_match(match_id)
    assert multiplayer_match is not None

    raw_referees: set[bytes] = await glob.redis.smembers(
        f"bancho:matches:{match_id}:referees",
    )
    referees = {int(referee) for referee in raw_referees}

    return referees


async def remove_referee(match_id: int, user_id: int) -> None:
    multiplayer_match = await get_match(match_id)
    assert multiplayer_match is not None

    await glob.redis.srem(f"bancho:matches:{match_id}:referees", user_id)


async def set_match_frame(
    match_id: int,
    slot_id: int,
    decoded_frame_data: dict[str, Any],
) -> None:
    multiplayer_match = await get_match(match_id)
    assert multiplayer_match is not None

    user_slot = await slot.get_slot(match_id, slot_id)
    assert user_slot is not None

    match_frame = decoded_frame_data | {
        "mods": user_slot["mods"]
        | multiplayer_match["mods"],  # Merge match mods and user mods
        "passed": user_slot["passed"],
        "team": user_slot["team"],
        "mode": multiplayer_match["game_mode"],
    }
    await glob.redis.set(
        f"bancho:matches:{match_id}:frames:{user_slot['user_id']}",
        orjson.dumps(match_frame),
    )


async def insert_match_frame(
    match_id: int,
    user_id: int,
) -> None:
    multiplayer_match = await get_match(match_id)
    assert multiplayer_match is not None

    match_frame = await glob.redis.get(
        f"bancho:matches:{match_id}:frames:{user_id}",
    )
    await glob.redis.delete(
        f"bancho:matches:{match_id}:frames:{user_id}",
    )
    assert match_frame is not None
    match_frame = orjson.loads(match_frame)

    await insert_match_game_score(
        match_id,
        multiplayer_match["current_game_id"],
        user_id,
        match_frame["mode"],
        match_frame["count300"],
        match_frame["count100"],
        match_frame["count50"],
        match_frame["countMiss"],
        match_frame["countGeki"],
        match_frame["countKatu"],
        match_frame["totalScore"],
        match_frame["maxCombo"],
        match_frame["mods"],
        match_frame["passed"],
        match_frame["team"],
    )


async def insert_match_game(
    match_id: int,
    beatmap_id: int,
    play_mode: int,
    mods: int,
    scoring_type: int,
    team_type: int,
) -> int:
    return await glob.db.execute(
        """INSERT INTO match_games
            (id, match_id, beatmap_id, mode, mods, scoring_type, team_type, start_time, end_time)
        VALUES
            (NULL, %s, %s, %s, %s, %s, %s, %s, NULL)
        """,
        [
            match_id,
            beatmap_id,
            play_mode,
            mods,
            scoring_type,
            team_type,
            datetime.now(),
        ],
    )


async def insert_match_game_score(
    match_id: int,
    game_id: int,
    user_id: int,
    mode: int,
    count_300: int,
    count_100: int,
    count_50: int,
    count_miss: int,
    count_geki: int,
    count_katu: int,
    score: int,
    max_combo: int,
    mods: int,
    passed: bool,
    team: int,
) -> None:
    accuracy = calculate_accuracy(
        mode=mode,
        n300=count_300,
        n100=count_100,
        n50=count_50,
        ngeki=count_geki,
        nkatu=count_katu,
        nmiss=count_miss,
    )

    await glob.db.execute(
        """
        INSERT INTO match_game_scores
            (id, match_id, game_id, user_id, mode, count_300, count_100, count_50, count_miss, count_geki, count_katu, score, accuracy, max_combo, mods, passed, team, timestamp)
        VALUES
            (NULL, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        [
            match_id,
            game_id,
            user_id,
            mode,
            count_300,
            count_100,
            count_50,
            count_miss,
            count_geki,
            count_katu,
            score,
            accuracy,
            max_combo,
            mods,
            passed,
            team,
            datetime.now(),
        ],
    )


async def finish_match_game(game_id: int) -> None:
    await glob.db.execute(
        "UPDATE match_games SET end_time = %s WHERE id = %s",
        [
            datetime.now(),
            game_id,
        ],
    )


async def finish_match(match_id: int) -> None:
    await glob.db.execute(
        "UPDATE matches SET end_time = %s WHERE id = %s",
        [
            datetime.now(),
            match_id,
        ],
    )


async def insert_match(
    match_name: str,
    match_history_private: bool,
) -> int:
    return await glob.db.execute(
        "INSERT INTO matches (id, name, private, start_time) VALUES (NULL, %s, %s, %s)",
        [
            match_name,
            int(match_history_private),
            datetime.now(),
        ],
    )


async def update_match_name(match_id: int, match_name: str) -> None:
    await glob.db.execute(
        "UPDATE matches SET name = %s WHERE id = %s",
        [
            match_name,
            match_id,
        ],
    )


async def insert_match_event(
    match_id: int,
    event_type: MatchEvents,
    game_id: int | None = None,
    user_id: int | None = None,
) -> None:
    await glob.db.execute(
        """
        INSERT INTO match_events
            (id, match_id, game_id, user_id, event_type, timestamp)
        VALUES
            (NULL, %s, %s, %s, %s, %s)
        """,
        [
            match_id,
            game_id,
            user_id,
            event_type.value,
            datetime.now(),
        ],
    )
