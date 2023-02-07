from __future__ import annotations

from objects import match
from objects.osuToken import Token

from redlock import RedLock

def handle(userToken: Token, _):
    # Make sure we are in a match
    if userToken["match_id"] is None:
        return

    # Make sure the match exists
    multiplayer_match = match.get_match(userToken['match_id'])
    if multiplayer_match is None:
        return

    # Host check
    if userToken['user_id'] != multiplayer_match["host_user_id"]:
        return

    match.start(multiplayer_match["match_id"])
