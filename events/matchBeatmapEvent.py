from __future__ import annotations

from objects import match, osuToken
from objects.osuToken import Token

from redlock import RedLock

def handle(userToken: Token, _, has_beatmap: bool):
    # Make sure we are in a match
    if userToken["match_id"] is None:
        return

    # Make sure the match exists
    multiplayer_match = match.get_match(userToken["match_id"])
    if multiplayer_match is None:
        return

    # Set has beatmap/no beatmap
    with RedLock(
        f"{match.make_key(userToken['match_id'])}:lock",
        retry_delay=100,
        retry_times=500,
    ):
        match.userHasBeatmap(
            multiplayer_match["match_id"],
            userToken["user_id"],
            has_beatmap,
        )
