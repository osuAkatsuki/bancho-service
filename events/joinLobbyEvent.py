from __future__ import annotations

from constants import serverPackets
from objects import match
from objects import osuToken
from objects.osuToken import Token


async def handle(userToken: Token, _):
    # Add user to users in lobby
    await osuToken.joinStream(userToken["token_id"], "lobby")

    # Send matches data
    for match_id in await match.get_match_ids():
        await osuToken.enqueue(
            userToken["token_id"],
            await serverPackets.createMatch(match_id),
        )
