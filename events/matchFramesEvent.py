from __future__ import annotations

from constants import clientPackets
from constants import serverPackets
from objects import glob
from objects.osuToken import token


def handle(userToken: token, rawPacketData: bytes):
    # Make sure we are in a match
    if userToken.matchID == -1:
        return

    # Make sure the match exists
    if userToken.matchID not in glob.matches.matches:
        return

    # Parse the data
    packetData = clientPackets.matchFrames(rawPacketData)

    with glob.matches.matches[userToken.matchID] as match:
        # Change slot id in packetData
        slotID = match.getUserSlotID(userToken.userID)
        assert slotID is not None

        # Update the score
        match.updateScore(slotID, packetData["totalScore"])
        match.updateHP(slotID, packetData["currentHp"])

        # Enqueue frames to who's playing
        glob.streams.broadcast(
            match.playingStreamName,
            serverPackets.matchFrames(slotID, rawPacketData),
        )
