from common.constants import mods
from constants import clientPackets, matchModModes, matchTeamTypes
from objects import glob
from objects.osuToken import token


def handle(userToken: token, rawPacketData: bytes):
    # Read new settings
    packetData = clientPackets.changeMatchSettings(rawPacketData)

    # Make sure the match exists
    if userToken.matchID not in glob.matches.matches:
        return

    # Host check
    with glob.matches.matches[userToken.matchID] as match:
        if userToken.userID != match.hostUserID:
            return

        # Update match settings
        match.matchName = packetData["matchName"]
        match.inProgress = packetData["inProgress"]
        match.matchPassword = packetData["matchPassword"]
        match.beatmapName = packetData["beatmapName"]
        match.beatmapID = packetData["beatmapID"]
        match.hostUserID = packetData["hostUserID"]
        match.gameMode = packetData["gameMode"]

        oldMods = match.mods
        oldBeatmapMD5 = match.beatmapMD5
        oldScoringType = match.matchScoringType
        oldMatchTeamType = match.matchTeamType
        oldMatchModMode = match.matchModMode

        match.mods = packetData["mods"]
        match.beatmapMD5 = packetData["beatmapMD5"]
        match.matchScoringType = packetData["scoringType"]
        match.matchTeamType = packetData["teamType"]
        match.matchModMode = packetData["freeMods"]

        if (
            oldMods != match.mods
            or oldBeatmapMD5 != match.beatmapMD5
            or oldScoringType != match.matchScoringType
            or oldMatchTeamType != match.matchTeamType
            or oldMatchModMode != match.matchModMode
        ):
            match.resetReady()

        if oldMatchModMode != match.matchModMode:
            # Match mode was changed.
            if match.matchModMode == matchModModes.NORMAL:
                # Freemods -> Central
                # Move mods from host -> match.
                is_host = lambda s: s.userID == match.hostUserID
                for slot in filter(is_host, match.slots):
                    match.mods = slot.mods  # yoink
                    break
            else:
                # Central -> Freemods
                # Move mods from match -> players.
                for slot in filter(lambda s: s.user, match.slots):
                    slot.mods = match.mods

                # Only keep speed-changing mods centralized.
                match.mods = match.mods & mods.SPEED_CHANGING
        """
        else: # Match mode unchanged.
            for slot in range(16):
                if match.matchModMode == matchModModes.FREE_MOD:
                    match.slots[slot].mods = packetData[f"slot{slot}Mods"]
                else:
                    match.slots[slot].mods = match.mods
        """

        # Initialize teams if team type changed
        if match.matchTeamType != oldMatchTeamType:
            match.initializeTeams()

        # Force no freemods if tag coop
        if match.matchTeamType in (matchTeamTypes.TAG_COOP, matchTeamTypes.TAG_TEAM_VS):
            match.matchModMode = matchModModes.NORMAL

        # Send updated settings
        match.sendUpdates()
