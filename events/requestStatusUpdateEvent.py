from __future__ import annotations

from constants import serverPackets
from objects import osuToken
from objects.osuToken import Token


def handle(userToken: Token, _):
    # Update cache and send new stats
    osuToken.updateCachedStats(userToken["token_id"])
    osuToken.enqueue(
        userToken["token_id"],
        serverPackets.userStats(userToken["user_id"]),
    )
