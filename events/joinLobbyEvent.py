from __future__ import annotations

from constants import serverPackets
from objects import match
from objects import osuToken
from objects.osuToken import Token


def handle(userToken: Token, _):
    # Add user to users in lobby
    osuToken.joinStream(userToken["token_id"], "lobby")

    # Send matches data
    for match_id in match.get_match_ids():
        osuToken.enqueue(userToken["token_id"], serverPackets.createMatch(match_id))
