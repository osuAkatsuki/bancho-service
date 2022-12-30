from __future__ import annotations

from constants import clientPackets
from constants import serverPackets
from objects import match, streamList
from objects.osuToken import token

from redlock import RedLock

def handle(userToken: token, rawPacketData: bytes):
    # Make sure we are in a match
    if userToken.matchID == -1:
        return

    # Make sure the match exists
    multiplayer_match = match.get_match(userToken.matchID)
    if multiplayer_match is None:
        return

    # Parse the data
    packetData = clientPackets.matchFrames(rawPacketData)

    with RedLock(
        f"{match.make_key(userToken.matchID)}:lock",
        retry_delay=50,
        retry_times=20,
    ):
        # Change slot id in packetData
        slot_id = match.getUserSlotID(multiplayer_match["match_id"], userToken.userID)
        assert slot_id is not None

        # Update the score
        match.updateScore(multiplayer_match["match_id"], slot_id, packetData["totalScore"])
        match.updateHP(multiplayer_match["match_id"], slot_id, packetData["currentHp"])

        # Enqueue frames to who's playing
        streamList.broadcast(
            match.create_playing_stream_name(multiplayer_match["match_id"]),
            serverPackets.matchFrames(slot_id, rawPacketData),
        )
