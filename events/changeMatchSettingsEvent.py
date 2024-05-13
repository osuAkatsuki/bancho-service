from __future__ import annotations

from common.constants import mods
from constants import clientPackets
from constants import matchModModes
from constants import matchTeamTypes
from objects import channelList
from objects import match
from objects import slot
from objects.osuToken import Token
from objects.redisLock import redisLock


async def handle(userToken: Token, rawPacketData: bytes) -> None:
    # Read new settings
    packetData = clientPackets.changeMatchSettings(rawPacketData)

    match_id = userToken["match_id"]
    if match_id is None:
        return

    async with redisLock(match.make_lock_key(match_id)):
        # Make sure the match exists
        multiplayer_match = await match.get_match(match_id)
        if multiplayer_match is None:
            return

        # Host check
        if userToken["user_id"] != multiplayer_match["host_user_id"]:
            return

        old_match_name = multiplayer_match["match_name"]
        old_mods = multiplayer_match["mods"]
        old_beatmap_md5 = multiplayer_match["beatmap_md5"]
        old_scoring_type = multiplayer_match["match_scoring_type"]
        old_match_team_type = multiplayer_match["match_team_type"]
        old_match_mod_mode = multiplayer_match["match_mod_mode"]

        # Update match settings
        multiplayer_match = await match.update_match(
            multiplayer_match["match_id"],
            match_name=packetData["matchName"],
            is_in_progress=packetData["inProgress"] == 1,
            match_password=packetData["matchPassword"],
            beatmap_name=packetData["beatmapName"],
            beatmap_id=packetData["beatmapID"],
            host_user_id=packetData["hostUserID"],
            game_mode=packetData["gameMode"],
            mods=packetData["mods"],
            beatmap_md5=packetData["beatmapMD5"],
            match_scoring_type=packetData["scoringType"],
            match_team_type=packetData["teamType"],
            match_mod_mode=packetData["freeMods"],
        )
        assert multiplayer_match is not None

        if (
            old_mods != multiplayer_match["mods"]
            or old_beatmap_md5 != multiplayer_match["beatmap_md5"]
            or old_scoring_type != multiplayer_match["match_scoring_type"]
            or old_match_team_type != multiplayer_match["match_team_type"]
            or old_match_mod_mode != multiplayer_match["match_mod_mode"]
        ):
            await match.resetReady(multiplayer_match["match_id"])

        if old_match_name != multiplayer_match["match_name"]:
            await channelList.updateChannel(
                f"#mp_{multiplayer_match['match_id']}",
                description=f"Multiplayer lobby for match {multiplayer_match['match_name']}",
            )

        if old_match_mod_mode != multiplayer_match["match_mod_mode"]:
            slots = await slot.get_slots(multiplayer_match["match_id"])

            # Match mode was changed.
            if multiplayer_match["match_mod_mode"] == matchModModes.NORMAL:
                # Freemods -> Central
                # Move mods from host -> match.
                for slot_id, _slot in enumerate(slots):
                    if _slot["user_id"] == multiplayer_match["host_user_id"]:
                        await match.update_match(
                            multiplayer_match["match_id"],
                            mods=_slot["mods"],
                        )
                        break
            else:
                # Central -> Freemods
                # Move mods from match -> players.
                for slot_id, _slot in enumerate(slots):
                    if _slot["user_token"]:
                        await slot.update_slot(
                            multiplayer_match["match_id"],
                            slot_id,
                            # removing speed changing mods would seem more correct,
                            # but that would mean switching back from freemods to central
                            # would remove speed changing mods from the match?
                            mods=multiplayer_match["mods"],
                        )

                # Only keep speed-changing mods centralized.
                await match.update_match(
                    multiplayer_match["match_id"],
                    mods=multiplayer_match["mods"] & mods.SPEED_CHANGING,
                )

        """
        else: # Match mode unchanged.
            for slot in range(16):
                if match.matchModMode == matchModModes.FREE_MOD:
                    match.slots[slot].mods = packetData[f"slot{slot}Mods"]
                else:
                    match.slots[slot].mods = match.mods
        """

        # Initialize teams if team type changed
        if multiplayer_match["match_team_type"] != old_match_team_type:
            await match.initializeTeams(multiplayer_match["match_id"])

        # Force no freemods if tag coop
        if multiplayer_match["match_team_type"] in (
            matchTeamTypes.TAG_COOP,
            matchTeamTypes.TAG_TEAM_VS,
        ):
            multiplayer_match["match_mod_mode"] = matchModModes.NORMAL

        # Send updated settings
        await match.sendUpdates(multiplayer_match["match_id"])
