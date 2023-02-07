from __future__ import annotations

from constants import serverPackets
from objects.osuToken import Token
from objects import osuToken

def handle(userToken: Token, _):
    # Update cache and send new stats
    osuToken.updateCachedStats(userToken["token_id"])
    osuToken.enqueue(userToken["token_id"], serverPackets.userStats(userToken["user_id"]))
