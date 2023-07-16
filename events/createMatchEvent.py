from __future__ import annotations

from common.log import logUtils as log
from constants import clientPackets
from constants import exceptions
from constants import serverPackets
from helpers import countryHelper
from objects import match
from objects import matchList
from objects import osuToken
from objects.redisLock import redisLock

from amplitude import BaseEvent
from uuid import uuid4
from objects import glob


def handle(token: osuToken.Token, rawPacketData: bytes):
    try:
        # Read packet data
        packetData = clientPackets.createMatch(rawPacketData)

        # Make sure the name is valid
        match_name = packetData["matchName"].strip()
        if not match_name:
            raise exceptions.matchCreateError()

        # Create a match object
        # TODO: Player number check
        match_id = matchList.createMatch(
            match_name,
            packetData["matchPassword"].strip(),
            packetData["beatmapID"],
            packetData["beatmapName"],
            packetData["beatmapMD5"],
            packetData["gameMode"],
            token["user_id"],
        )

        # Make sure the match has been created
        multiplayer_match = match.get_match(match_id)
        if multiplayer_match is None:
            raise exceptions.matchCreateError()

        with redisLock(f"{match.make_key(match_id)}:lock"):
            # Join that match
            osuToken.joinMatch(token["token_id"], match_id)

            # Give host to match creator
            match.setHost(match_id, token["user_id"])
            match.sendUpdates(match_id)
            match.changePassword(match_id, packetData["matchPassword"])

        insert_id = str(uuid4())
        glob.amplitude.track(
            BaseEvent(
                event_type="create_multiplayer_match",
                user_id=str(token["user_id"]),
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
                location_lat=token["latitude"],
                location_lng=token["longitude"],
                ip=token["ip"],
                country=countryHelper.getCountryLetters(token["country"]),
                insert_id=insert_id,
            )
        )

    except exceptions.matchCreateError:
        log.error("Error while creating match!")
        osuToken.enqueue(token["token_id"], serverPackets.matchJoinFail)
