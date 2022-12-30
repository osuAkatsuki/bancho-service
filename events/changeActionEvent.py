from __future__ import annotations

from common.constants import actions
from common.constants import mods
from common.ripple import userUtils
from constants import clientPackets
from constants import serverPackets
from objects import glob
from objects.osuToken import token


def handle(userToken: token, rawPacketData: bytes):
    # Make sure we are not banned
    # if userUtils.isBanned(userID):
    # 	userToken.enqueue(serverPackets.loginBanned)
    # 	return

    # Send restricted message if needed
    # if userToken.restricted:
    # 	userToken.checkRestricted(True)

    # Change action packet
    packetData = clientPackets.userActionChange(rawPacketData)

    """ If we are not in spectate status but we're spectating someone, stop spectating
    if userToken.spectating != 0 and userToken.actionID != actions.WATCHING and userToken.actionID != actions.IDLE and userToken.actionID != actions.AFK:
        userToken.stopSpectating()

    # If we are not in multiplayer but we are in a match, part match
    if userToken.matchID != -1 and userToken.actionID != actions.MULTIPLAYING and userToken.actionID != actions.MULTIPLAYER and userToken.actionID != actions.AFK:
        userToken.partMatch()
    """

    relax_in_mods: bool = packetData["actionMods"] & mods.RELAX != 0
    autopilot_in_mods: bool = packetData["actionMods"] & mods.AUTOPILOT != 0

    # Update cached stats if relax/autopilot status changed

    if relax_in_mods != userToken.relax:
        userToken.relax = relax_in_mods
        userToken.updateCachedStats()

    if autopilot_in_mods != userToken.autopilot:
        userToken.autopilot = autopilot_in_mods
        userToken.updateCachedStats()

    # Update cached stats if our pp changed if we've just submitted a score or we've changed gameMode
    if userToken.actionID in {
        actions.PLAYING,
        actions.MULTIPLAYING,
    } or userToken.pp != userUtils.getPP(
        userToken.userID,
        userToken.gameMode,
        userToken.relax,
        userToken.autopilot,
    ):
        userToken.updateCachedStats()

    if userToken.gameMode != packetData["gameMode"]:
        userToken.gameMode = packetData["gameMode"]
        userToken.updateCachedStats()

    # Always update action id, text, md5 and beatmapID
    userToken.actionID = packetData["actionID"]
    userToken.actionText = packetData["actionText"]
    userToken.actionMd5 = packetData["actionMd5"]
    userToken.actionMods = packetData["actionMods"]
    userToken.beatmapID = packetData["beatmapID"]

    # Enqueue our new user panel and stats to us and our spectators
    recipients = [userToken]
    if userToken.spectators:
        for i in userToken.spectators:
            if i in glob.tokens.tokens:
                recipients.append(glob.tokens.tokens[i])

    for i in recipients:
        if not i:
            continue

        # Force our own packet
        force = i == userToken
        i.enqueue(serverPackets.userPanel(userToken.userID, force))
        i.enqueue(serverPackets.userStats(userToken.userID, force))
