from __future__ import annotations

from constants import clientPackets
from objects import match
from objects.osuToken import Token
from objects.redisLock import redisLock


async def handle(userToken: Token, rawPacketData: bytes):
    # Make sure we are in a match
    if userToken["match_id"] is None:
        return

    # Send invite
    async with redisLock(match.make_lock_key(userToken["match_id"])):
        # Make sure the match exists
        multiplayer_match = await match.get_match(userToken["match_id"])
        if multiplayer_match is None:
            return

        await match.invite(
            multiplayer_match["match_id"],
            userToken["user_id"],
            clientPackets.matchInvite(rawPacketData)["userID"],
        )
