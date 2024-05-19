from __future__ import annotations

from amplitude import BaseEvent

from constants import clientPackets
from constants import serverPackets
from helpers import countryHelper
from objects import glob
from objects import match
from objects import osuToken
from objects.osuToken import Token
from objects.redisLock import redisLock


async def handle(userToken: Token, rawPacketData: bytes) -> None:
    # read packet data
    packetData = clientPackets.joinMatch(rawPacketData)
    matchID = packetData["matchID"]
    password = packetData["password"]

    async with redisLock(match.make_lock_key(matchID)):
        # Make sure the match exists
        multiplayer_match = await match.get_match(matchID)
        if multiplayer_match is None:
            await osuToken.enqueue(userToken["token_id"], serverPackets.matchJoinFail)
            return

        # Check password
        if multiplayer_match["match_password"]:
            if password != multiplayer_match["match_password"]:
                await osuToken.enqueue(
                    userToken["token_id"],
                    serverPackets.matchJoinFail,
                )
                return

        # Password is correct, join match
        await osuToken.joinMatch(userToken["token_id"], matchID)

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
                event_type="join_multiplayer_match",
                user_id=str(userToken["user_id"]),
                device_id=userToken["amplitude_device_id"],
                event_properties=amplitude_event_props,
                location_lat=userToken["latitude"],
                location_lng=userToken["longitude"],
                ip=userToken["ip"],
                country=countryHelper.osu_code_to_iso_code(userToken["country"]),
            ),
        )
