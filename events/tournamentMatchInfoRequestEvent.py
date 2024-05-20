from __future__ import annotations

from common.log import logger
from constants import clientPackets
from constants import serverPackets
from objects import match
from objects import osuToken
from objects.osuToken import Token
from objects.redisLock import redisLock


async def handle(userToken: Token, rawPacketData: bytes) -> None:
    if not userToken["tournament"]:
        return

    packetData = clientPackets.tournamentMatchInfoRequest(rawPacketData)

    match_id = packetData["matchID"]

    async with redisLock(match.make_lock_key(match_id)):
        multiplayer_match = await match.get_match(match_id)
        if multiplayer_match is None:
            return

        packet_data = await serverPackets.updateMatch(match_id, censored=True)
        assert packet_data is not None

        await osuToken.enqueue(userToken["token_id"], packet_data)

    logger.info(
        "Tournament client requested match information",
        extra={
            "user_id": userToken["user_id"],
            "match_id": match_id,
        },
    )
