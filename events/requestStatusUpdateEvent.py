from __future__ import annotations

from constants import serverPackets
from objects import osuToken
from objects.osuToken import Token


async def handle(userToken: Token, rawPacketData: bytes) -> None:
    # Update cache and send new stats
    await osuToken.updateCachedStats(userToken["token_id"])
    await osuToken.enqueue(
        userToken["token_id"],
        await serverPackets.userStats(token_id=userToken["token_id"]),
    )
