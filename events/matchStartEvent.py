from __future__ import annotations

from objects import match
from objects.osuToken import token

from redlock import RedLock

def handle(userToken: token, _):
    # Make sure we are in a match
    if userToken.matchID == -1:
        return

    # Make sure the match exists
    multiplayer_match = match.get_match(userToken.matchID)
    if multiplayer_match is None:
        return

    with RedLock(
        f"{match.make_key(userToken.matchID)}:lock",
        retry_delay=50,
        retry_times=20,
    ):
        # Host check
        if userToken.userID != multiplayer_match["host_user_id"]:
            return

        match.start(multiplayer_match["match_id"])
