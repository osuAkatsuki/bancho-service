from __future__ import annotations

from constants import clientPackets
from constants import serverPackets
from objects import match, streamList
from objects.osuToken import Token

from redlock import RedLock

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

    # Change slot id in packetData
    slot_id = match.getUserSlotID(multiplayer_match["match_id"], userToken["user_id"])
    assert slot_id is not None

    # Update the score
    match.updateScore(multiplayer_match["match_id"], slot_id, packetData["totalScore"])
    match.updateHP(multiplayer_match["match_id"], slot_id, packetData["currentHp"])

    # Enqueue frames to who's playing
    streamList.broadcast(
        match.create_playing_stream_name(multiplayer_match["match_id"]),
        serverPackets.matchFrames(slot_id, rawPacketData),
    )
