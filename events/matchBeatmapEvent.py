from __future__ import annotations

from objects import match
from objects.osuToken import Token
from objects.redisLock import redisLock


def handle(userToken: Token, _, has_beatmap: bool):
    # Make sure we are in a match
    if userToken["match_id"] is None:
        return

    # Make sure the match exists
    multiplayer_match = match.get_match(userToken["match_id"])
    if multiplayer_match is None:
        return

    with redisLock(f"{match.make_key(userToken['match_id'])}:lock"):
        # Set has beatmap/no beatmap
        match.userHasBeatmap(
            multiplayer_match["match_id"],
            userToken["user_id"],
            has_beatmap,
        )
