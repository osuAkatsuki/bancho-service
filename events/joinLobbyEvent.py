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
        multiplayer_match = await match.get_match(match_id)
        if multiplayer_match is None:
            continue

        await osuToken.enqueue(
            userToken["token_id"],
            await serverPackets.createMatch(multiplayer_match),
        )
