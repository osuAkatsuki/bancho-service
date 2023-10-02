from __future__ import annotations

from constants import clientPackets
from constants import serverPackets
from objects import match
from objects import streamList
from objects.osuToken import Token
from objects.redisLock import redisLock


async def handle(userToken: Token, rawPacketData: bytes):
    # Make sure we are in a match
    if userToken["match_id"] is None:
        return

    # Parse the data
    packetData = clientPackets.matchFrames(rawPacketData)

    async with redisLock(f"{match.make_key(userToken['match_id'])}:lock"):
        # Make sure the match exists
        multiplayer_match = await match.get_match(userToken["match_id"])
        if multiplayer_match is None:
            return

        # Change slot id in packetData
        slot_id = await match.getUserSlotID(
            multiplayer_match["match_id"],
            userToken["user_id"],
        )
        assert slot_id is not None

        # Update the score
        await match.updateScore(
            multiplayer_match["match_id"],
            slot_id,
            packetData["totalScore"],
        )
        await match.updateHP(
            multiplayer_match["match_id"], slot_id, packetData["currentHp"],
        )

        # Enqueue frames to who's playing
        await streamList.broadcast(
            match.create_playing_stream_name(multiplayer_match["match_id"]),
            serverPackets.matchFrames(slot_id, rawPacketData),
        )
