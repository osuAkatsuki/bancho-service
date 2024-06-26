from __future__ import annotations

from constants import clientPackets
from constants import serverPackets
from objects import match
from objects import osuToken
from objects.osuToken import Token
from objects.redisLock import redisLock


async def handle(userToken: Token, rawPacketData: bytes) -> None:
    packetData = clientPackets.tournamentMatchInfoRequest(rawPacketData)

    match_id = packetData["matchID"]

    async with redisLock(match.make_lock_key(match_id)):
        multiplayer_match = await match.get_match(match_id)
        if multiplayer_match is None or not userToken["tournament"]:
            return

        packet_data = await serverPackets.updateMatch(match_id)
        if packet_data is None:
            # TODO: is this correct behaviour?
            # ripple was doing this before the stateless refactor,
            # but i'm pretty certain the osu! client won't like this.
            await osuToken.enqueue(userToken["token_id"], b"")
            return None

        await osuToken.enqueue(userToken["token_id"], packet_data)
