from __future__ import annotations

from constants import serverPackets
from objects import glob


def handle(userToken, _):
    # Add user to users in lobby
    userToken.joinStream("lobby")

    # Send matches data
    for key, _ in glob.matches.matches.items():
        userToken.enqueue(serverPackets.createMatch(key))
