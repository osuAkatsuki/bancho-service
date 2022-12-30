from __future__ import annotations

from constants import serverPackets
from objects import match
from objects.osuToken import token


def handle(userToken: token, _):
    # Add user to users in lobby
    userToken.joinStream("lobby")

    # Send matches data
    for match_id in match.get_match_ids():
        userToken.enqueue(serverPackets.createMatch(match_id))
