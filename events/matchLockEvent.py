from __future__ import annotations

from constants import clientPackets
from objects import match
from objects.osuToken import Token
from objects.redisLock import redisLock


async def handle(userToken: Token, rawPacketData: bytes) -> None:
    # Get packet data
    packetData = clientPackets.lockSlot(rawPacketData)

    if userToken["match_id"] is None:
        return

    async with redisLock(match.make_lock_key(userToken["match_id"])):
        # Make sure the match exists
        multiplayer_match = await match.get_match(userToken["match_id"])
        if multiplayer_match is None:
            return

        # Host check
        if userToken["user_id"] != multiplayer_match["host_user_id"]:
            return

        # Make sure we aren't locking our slot
        ourSlot = await match.getUserSlotID(
            multiplayer_match["match_id"],
            userToken["user_id"],
        )
        if packetData["slotID"] == ourSlot:
            return

        # Lock/Unlock slot
        await match.toggleSlotLocked(
            multiplayer_match["match_id"],
            packetData["slotID"],
        )
