from __future__ import annotations

from objects import match
from objects.osuToken import Token
from objects.redisLock import redisLock


async def handle(userToken: Token, rawPacketData: bytes) -> None:
    # Make sure we are in a match
    if userToken["match_id"] is None:
        return

    # Change team
    async with redisLock(match.make_lock_key(userToken["match_id"])):
        # Make sure the match exists
        multiplayer_match = await match.get_match(userToken["match_id"])
        if multiplayer_match is None:
            return

        await match.changeTeam(multiplayer_match["match_id"], userToken["user_id"])
