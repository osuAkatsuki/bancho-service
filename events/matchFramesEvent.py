from __future__ import annotations

import logging

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

    if userToken["match_slot_id"] is None:
        logging.warning(
            "User is in a match but has no slot id",
            extra={"user_id": userToken["user_id"]},
        )
        return

    await match.set_match_frame(
        multiplayer_match["match_id"],
        userToken["match_slot_id"],
        packetData,
    )

    # Update the score
    user_failed = packetData["currentHp"] == 254
    await slot.update_slot(
        multiplayer_match["match_id"],
        userToken["match_slot_id"],
        score=packetData["totalScore"],
        failed=user_failed,
    )

    # Enqueue frames to who's playing
    await stream_messages.broadcast_data(
        match.create_playing_stream_name(multiplayer_match["match_id"]),
        serverPackets.matchFrames(userToken["match_slot_id"], rawPacketData),
    )
