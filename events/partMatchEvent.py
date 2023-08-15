from __future__ import annotations

from amplitude import BaseEvent

from helpers import countryHelper
from objects import glob
from objects import match
from objects import osuToken
from objects.osuToken import Token


def handle(userToken: Token, _=None):
    matchID = userToken["match_id"]
    if matchID is None:
        return

    # Make sure the match exists
    multiplayer_match = match.get_match(matchID)
    if multiplayer_match is None:
        return

    osuToken.leaveMatch(userToken["token_id"])

    glob.amplitude.track(
        BaseEvent(
            event_type="leave_multiplayer_match",
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
