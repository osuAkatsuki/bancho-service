from __future__ import annotations

from amplitude import BaseEvent

from objects import glob
from objects import match
from objects.osuToken import Token
from objects.redisLock import redisLock


async def handle(userToken: Token, rawPacketData: bytes) -> None:
    # Make sure we are in a match
    if userToken["match_id"] is None:
        return

    async with redisLock(match.make_lock_key(userToken["match_id"])):
        # Make sure the match exists
        multiplayer_match = await match.get_match(userToken["match_id"])
        if multiplayer_match is None:
            return

        # Host check
        if userToken["user_id"] != multiplayer_match["host_user_id"]:
            return

        await match.start(multiplayer_match["match_id"])

    if glob.amplitude is not None:
        amplitude_event_props = {
            "match": {
                "match_id": multiplayer_match["match_id"],
                "match_name": multiplayer_match["match_name"],
                # "match_password": multiplayer_match["match_password"],
                "beatmap_id": multiplayer_match["beatmap_id"],
                "beatmap_name": multiplayer_match["beatmap_name"],
                "beatmap_md5": multiplayer_match["beatmap_md5"],
                "game_mode": multiplayer_match["game_mode"],
                "host_user_id": multiplayer_match["host_user_id"],
                "mods": multiplayer_match["mods"],
                "match_scoring_type": multiplayer_match["match_scoring_type"],
                "match_team_type": multiplayer_match["match_team_type"],
                "match_mod_mode": multiplayer_match["match_mod_mode"],
                "seed": multiplayer_match["seed"],
                "is_tourney": multiplayer_match["is_tourney"],
                "is_locked": multiplayer_match["is_locked"],
                "is_starting": multiplayer_match["is_starting"],
                "is_in_progress": multiplayer_match["is_in_progress"],
                "creation_time": multiplayer_match["creation_time"],
            },
            "source": "bancho-service",
        }
        glob.amplitude.track(
            BaseEvent(
                event_type="start_multiplayer_match",
                user_id=str(userToken["user_id"]),
                device_id=userToken["amplitude_device_id"],
                event_properties=amplitude_event_props,
            ),
        )
