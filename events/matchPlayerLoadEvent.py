from __future__ import annotations

from objects import match
from objects.osuToken import Token

from redlock import RedLock

def handle(userToken: Token, _):
    # Make sure we are in a match
    if userToken["match_id"] is None:
        return

    # Make sure the match exists
    multiplayer_match = match.get_match(userToken["match_id"])
    if multiplayer_match is None:
        return

    # Set our load status
    match.playerLoaded(multiplayer_match["match_id"], userToken["user_id"])
