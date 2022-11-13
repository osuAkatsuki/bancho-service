from __future__ import annotations

from constants import clientPackets
from objects import glob
from objects.osuToken import token


def handle(userToken: token, rawPacketData: bytes):
    # Get packet data
    packetData = clientPackets.lockSlot(rawPacketData)

    # Make sure the match exists
    matchID = userToken.matchID
    if matchID not in glob.matches.matches:
        return

    with glob.matches.matches[matchID] as match:
        # Host check
        if userToken.userID != match.hostUserID:
            return

        # Make sure we aren't locking our slot
        ourSlot = match.getUserSlotID(userToken.userID)
        if packetData["slotID"] == ourSlot:
            return

        # Lock/Unlock slot
        match.toggleSlotLocked(packetData["slotID"])
