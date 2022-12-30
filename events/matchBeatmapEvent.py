from __future__ import annotations

from objects import match
from objects.osuToken import token

from redlock import RedLock

def handle(userToken: token, _, has_beatmap: bool):
    # Make sure we are in a match
    if userToken.matchID == -1:
        return

    # Make sure the match exists
    multiplayer_match = match.get_match(userToken.matchID)
    if multiplayer_match is None:
        return

    # Set has beatmap/no beatmap
    with RedLock(
        f"{match.make_key(userToken.matchID)}:lock",
        retry_delay=50,
        retry_times=20,
    ):
        match.userHasBeatmap(
            multiplayer_match["match_id"],
            userToken.userID,
            has_beatmap,
        )
