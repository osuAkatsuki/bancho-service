from __future__ import annotations

from constants import clientPackets
from objects import match
from objects.osuToken import Token
from objects.redisLock import redisLock


async def handle(userToken: Token, rawPacketData: bytes) -> None:
    # Read packet data. Same structure as changeMatchSettings
    packetData = clientPackets.changeMatchSettings(rawPacketData)

    match_id = userToken["match_id"]
    if match_id is None:
        return

    async with redisLock(match.make_lock_key(match_id)):
        # Make sure the match exists
        multiplayer_match = await match.get_match(match_id)
        if multiplayer_match is None:
            return

        # Host check
        if match_id != multiplayer_match["host_user_id"]:
            return

        # Update match password
        await match.changePassword(
            multiplayer_match["match_id"],
            packetData["matchPassword"],
        )
