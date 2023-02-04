from __future__ import annotations

from constants import clientPackets
from objects import match
from objects.osuToken import Token

from redlock import RedLock


def handle(userToken: Token, rawPacketData: bytes):
    # Get packet data
    packetData = clientPackets.lockSlot(rawPacketData)

    # Make sure the match exists
    multiplayer_match = match.get_match(userToken["match_id"])
    if multiplayer_match is None:
        return

    # Host check
    if userToken["user_id"] != multiplayer_match["host_user_id"]:
        return

    # Make sure we aren't locking our slot
    ourSlot = match.getUserSlotID(multiplayer_match["match_id"], userToken["user_id"])
    if packetData["slotID"] == ourSlot:
        return

    # Lock/Unlock slot
    match.toggleSlotLocked(multiplayer_match["match_id"], packetData["slotID"])
