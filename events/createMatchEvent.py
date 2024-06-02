from __future__ import annotations

from amplitude import BaseEvent

from adapters import feature_flags
from common.log import logger
from constants import clientPackets
from constants import exceptions
from constants import serverPackets
from helpers import countryHelper
from objects import glob
from objects import match
from objects import matchList
from objects import osuToken
from objects.redisLock import redisLock


class MatchCreationDisabledError(Exception): ...


async def handle(token: osuToken.Token, rawPacketData: bytes) -> None:
    try:
        # Read packet data
        packetData = clientPackets.createMatch(rawPacketData)

        # Make sure the name is valid
        match_name = packetData["matchName"].strip()
        if not match_name:
            raise exceptions.matchCreateError()

        match_creation_enabled = feature_flags.is_feature_enabled(
            feature_name="osu_match_creation_enabled",
            user_id=str(token["user_id"]),
            device_id=token["amplitude_device_id"],
        )
        if not (match_creation_enabled or osuToken.is_staff(token["privileges"])):
            raise MatchCreationDisabledError()

        # Create a match object
        # TODO: Player number check
        multiplayer_match = await matchList.createMatch(
            match_name,
            packetData["matchPassword"].strip(),
            packetData["beatmapID"],
            packetData["beatmapName"],
            packetData["beatmapMD5"],
            packetData["gameMode"],
            token["user_id"],
        )

        async with redisLock(match.make_lock_key(multiplayer_match["match_id"])):
            # Join that match
            await osuToken.joinMatch(token["token_id"], multiplayer_match["match_id"])

            # Give host to match creator
            await match.setHost(multiplayer_match["match_id"], token["user_id"])
            await match.sendUpdates(multiplayer_match["match_id"])
            await match.changePassword(
                multiplayer_match["match_id"],
                packetData["matchPassword"],
            )

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
                    event_type="create_multiplayer_match",
                    user_id=str(token["user_id"]),
                    device_id=token["amplitude_device_id"],
                    event_properties=amplitude_event_props,
                    location_lat=token["latitude"],
                    location_lng=token["longitude"],
                    ip=token["ip"],
                    country=countryHelper.osu_code_to_iso_code(token["country"]),
                ),
            )

    except exceptions.matchCreateError:
        logger.exception("An error occurred while creating a multiplayer match")
        await osuToken.enqueue(token["token_id"], serverPackets.matchJoinFail)
    except MatchCreationDisabledError:
        await osuToken.enqueue(
            token["token_id"],
            (
                serverPackets.matchJoinFail
                + serverPackets.notification(
                    "Match creation is disabled. Please try again later!",
                )
            ),
        )
