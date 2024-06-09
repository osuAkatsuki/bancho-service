from __future__ import annotations

from constants import clientPackets
from constants import serverPackets
from objects import match
from objects import osuToken
from objects import slot
from objects import stream_messages
from objects.osuToken import Token


async def handle(userToken: Token, rawPacketData: bytes) -> None:
    # Make sure we are in a match
    if userToken["match_id"] is None:
        return

    # Parse the data
    packetData = clientPackets.matchFrames(rawPacketData)

    # Make sure the match exists
    multiplayer_match = await match.get_match(userToken["match_id"])
    if multiplayer_match is None:
        return

    # Change slot id in packetData
    # TODO: Once match_slot_id is 100% available in production tokens,
    #       we should be able to decommission the use of `getUserSlotID()`
    match_slot_id = userToken.get("match_slot_id")
    if match_slot_id is None:
        match_slot_id = await match.getUserSlotID(
            multiplayer_match["match_id"],
            userToken["user_id"],
        )
        assert match_slot_id is not None
        maybe_token = await osuToken.update_token(
            userToken["token_id"],
            match_slot_id=match_slot_id,
        )
        assert maybe_token is not None
        userToken = maybe_token

    await match.set_match_frame(
        multiplayer_match["match_id"],
        match_slot_id,
        packetData,
    )

    # Update the score
    user_failed = packetData["currentHp"] == 254
    await slot.update_slot(
        multiplayer_match["match_id"],
        match_slot_id,
        score=packetData["totalScore"],
        failed=user_failed,
    )

    # Enqueue frames to who's playing
    await stream_messages.broadcast_data(
        match.create_playing_stream_name(multiplayer_match["match_id"]),
        serverPackets.matchFrames(match_slot_id, rawPacketData),
    )
