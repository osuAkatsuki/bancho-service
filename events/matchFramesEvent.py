from __future__ import annotations

from constants import clientPackets
from constants import serverPackets
from objects import match
from objects import streamList
from objects.osuToken import Token
from objects.redisLock import redisLock


def handle(userToken: Token, rawPacketData: bytes):
    # Make sure we are in a match
    if userToken["match_id"] is None:
        return

    # Make sure the match exists
    multiplayer_match = match.get_match(userToken["match_id"])
    if multiplayer_match is None:
        return

    # Parse the data
    packetData = clientPackets.matchFrames(rawPacketData)

    with redisLock(f"{match.make_key(userToken['match_id'])}:lock"):
        # Change slot id in packetData
        slot_id = match.getUserSlotID(
            multiplayer_match["match_id"],
            userToken["user_id"],
        )
        assert slot_id is not None

        # Update the score
        match.updateScore(
            multiplayer_match["match_id"],
            slot_id,
            packetData["totalScore"],
        )
        match.updateHP(multiplayer_match["match_id"], slot_id, packetData["currentHp"])

        # Enqueue frames to who's playing
        streamList.broadcast(
            match.create_playing_stream_name(multiplayer_match["match_id"]),
            serverPackets.matchFrames(slot_id, rawPacketData),
        )
