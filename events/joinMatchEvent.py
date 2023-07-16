from __future__ import annotations

from common.log import logUtils as log
from constants import clientPackets
from constants import serverPackets
from helpers import countryHelper
from objects import match
from objects import osuToken
from objects.osuToken import Token
from objects.redisLock import redisLock

from amplitude import BaseEvent
from uuid import uuid4
from objects import glob

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

    insert_id = str(uuid4())
    glob.amplitude.track(
        BaseEvent(
            event_type="join_multiplayer_match",
            user_id=str(userToken["user_id"]),
            device_id=None,
            event_properties={
                "match_id": multiplayer_match["match_id"],
                "match_name": multiplayer_match["match_name"],
                "beatmap_id": multiplayer_match["beatmap_id"],
                "beatmap_name": multiplayer_match["beatmap_name"],
                "beatmap_md5": multiplayer_match["beatmap_md5"],
                "game_mode": multiplayer_match["game_mode"],
                "host_user_id": multiplayer_match["host_user_id"],
                "mods": multiplayer_match["mods"],
                "is_tourney": multiplayer_match["is_tourney"],
                "is_locked": multiplayer_match["is_locked"],
                "is_in_progress": multiplayer_match["is_in_progress"],
                "creation_time": multiplayer_match["creation_time"],
            },
            location_lat=userToken["latitude"],
            location_lng=userToken["longitude"],
            ip=userToken["ip"],
            country=countryHelper.getCountryLetters(userToken["country"]),
            insert_id=insert_id,
        )
    )
