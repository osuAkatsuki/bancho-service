from __future__ import annotations

from objects import match
from objects.osuToken import Token
from objects.redisLock import redisLock


# NOTE: This is invoked not directly from mainHandler, but rather from
# the matchNoBeatmapEvent and matchHasBeatmapEvent event handlers, to
# allow for more code reuse.


async def handle(
    userToken: Token,
    rawPacketData: bytes,
    *,
    has_beatmap: bool,
) -> None:
    # Make sure we are in a match
    if userToken["match_id"] is None:
        return

    async with redisLock(match.make_lock_key(userToken["match_id"])):
        # Make sure the match exists
        multiplayer_match = await match.get_match(userToken["match_id"])
        if multiplayer_match is None:
            return

        # Set has beatmap/no beatmap
        await match.userHasBeatmap(
            multiplayer_match["match_id"],
            userToken["user_id"],
            has_beatmap,
        )
