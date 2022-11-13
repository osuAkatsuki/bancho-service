from __future__ import annotations

from common.constants import mods
from constants import clientPackets
from constants import matchModModes
from objects import glob
from objects.osuToken import token


def handle(userToken: token, rawPacketData: bytes):
    # Get packet data
    packetData = clientPackets.changeMods(rawPacketData)

    # Make sure the match exists
    if userToken.matchID not in glob.matches.matches:
        return

    # Set slot or match mods according to modType
    with glob.matches.matches[userToken.matchID] as match:
        if match.matchModMode == matchModModes.FREE_MOD:
            if userToken.userID == match.hostUserID:
                # Allow host to apply speed changing mods.
                match.changeMods(packetData["mods"] & mods.SPEED_CHANGING)

            # Set slot mods
            slotID = match.getUserSlotID(userToken.userID)
            if slotID is not None:  # Apply non-speed changing mods.
                match.setSlotMods(slotID, packetData["mods"] & ~mods.SPEED_CHANGING)
        else:
            # Not freemod, set match mods
            match.changeMods(packetData["mods"])
