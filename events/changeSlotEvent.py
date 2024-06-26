from __future__ import annotations

from constants import clientPackets
from objects import match
from objects import osuToken
from objects.osuToken import Token
from objects.redisLock import redisLock


async def handle(userToken: Token, rawPacketData: bytes) -> None:
    match_id = userToken["match_id"]
    if match_id is None:
        return

    packetData = clientPackets.changeSlot(rawPacketData)

    async with redisLock(match.make_lock_key(match_id)):
        multiplayer_match = await match.get_match(match_id)
        if multiplayer_match is None:
            return

        await match.userChangeSlot(
            multiplayer_match["match_id"],
            userToken["user_id"],
            packetData["slotID"],
        )

        maybe_token = await osuToken.update_token(
            userToken["token_id"],
            match_slot_id=packetData["slotID"],
        )
        assert maybe_token is not None
        userToken = maybe_token
