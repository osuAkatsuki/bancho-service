from __future__ import annotations

from constants import serverPackets
from objects.osuToken import token


def handle(userToken: token, _):
    # Update cache and send new stats
    userToken.updateCachedStats()
    userToken.enqueue(serverPackets.userStats(userToken.userID))
