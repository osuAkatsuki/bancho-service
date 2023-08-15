from __future__ import annotations

from amplitude import BaseEvent

from common.log import logUtils as log
from constants import clientPackets
from constants import serverPackets
from helpers import countryHelper
from objects import glob
from objects import match
from objects import osuToken
from objects.osuToken import Token
from objects.redisLock import redisLock


def handle(userToken: Token, rawPacketData: bytes):
    # read packet data
    packetData = clientPackets.joinMatch(rawPacketData)
    matchID = packetData["matchID"]
    password = packetData["password"]

    # Make sure the match exists
    multiplayer_match = match.get_match(matchID)
    if multiplayer_match is None:
        osuToken.enqueue(userToken["token_id"], serverPackets.matchJoinFail)
        return

    with redisLock(f"{match.make_key(matchID)}:lock"):
        # Check password
        if multiplayer_match["match_password"] not in ("", password):
            osuToken.enqueue(userToken["token_id"], serverPackets.matchJoinFail)
            log.warning(
                f"{userToken['username']} has tried to join a mp room, but he typed the wrong password.",
            )
            return

        # Password is correct, join match
        osuToken.joinMatch(userToken["token_id"], matchID)

    glob.amplitude.track(
        BaseEvent(
            event_type="join_multiplayer_match",
            user_id=str(userToken["user_id"]),
            device_id=userToken["amplitude_device_id"],
            event_properties={
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
            },
            location_lat=userToken["latitude"],
            location_lng=userToken["longitude"],
            ip=userToken["ip"],
            country=countryHelper.getCountryLetters(userToken["country"]),
        ),
    )
