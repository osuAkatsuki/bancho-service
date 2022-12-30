from __future__ import annotations

from common.constants import mods
from constants import clientPackets
from constants import matchModModes
from objects import match
from objects.osuToken import Token
from redlock import RedLock


def handle(userToken: Token, rawPacketData: bytes):
    # Get packet data
    packetData = clientPackets.changeMods(rawPacketData)

    match_id = userToken["match_id"]
    if match_id is None:
        return None

    # Make sure the match exists
    multiplayer_match = match.get_match(match_id)
    if multiplayer_match is None:
        return None

    # Set slot or match mods according to modType
    with RedLock(
        f"{match.make_key(match_id)}:lock",
        retry_delay=50, # ms
        retry_times=20,
    ):
        if multiplayer_match["match_mod_mode"] == matchModModes.FREE_MOD:
            if userToken["user_id"] == multiplayer_match["host_user_id"]:
                # Allow host to apply speed changing mods.
                match.changeMods(multiplayer_match["match_id"], packetData["mods"] & mods.SPEED_CHANGING)

            # Set slot mods
            slot_id = match.getUserSlotID(multiplayer_match["match_id"], userToken["user_id"])
            if slot_id is not None:  # Apply non-speed changing mods.
                match.setSlotMods(
                    multiplayer_match["match_id"],
                    slot_id,
                    packetData["mods"] & ~mods.SPEED_CHANGING,
                )
        else:
            # Not freemod, set match mods
            match.changeMods(multiplayer_match["match_id"], packetData["mods"])
