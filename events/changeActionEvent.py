from __future__ import annotations

from common.constants import actions
from common.constants import mods
from common.ripple import userUtils
from constants import clientPackets
from constants import serverPackets
from objects import glob
from objects import osuToken
from objects.osuToken import Token


def handle(userToken: Token, rawPacketData: bytes):
    # Make sure we are not banned
    # if userUtils.isBanned(userID):
    # 	userToken.enqueue(serverPackets.loginBanned)
    # 	return

    # Send restricted message if needed
    # if userToken["restricted"]:
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
    should_update_cached_stats = False

    if relax_in_mods != userToken["relax"]:
        userToken["relax"] = relax_in_mods
        should_update_cached_stats = True

    if autopilot_in_mods != userToken["autopilot"]:
        userToken["autopilot"] = autopilot_in_mods
        should_update_cached_stats = True

    # Update cached stats if our pp changed if we've just submitted a score or we've changed gameMode
    if userToken["action_id"] in {actions.PLAYING, actions.MULTIPLAYING} or userToken[
        "pp"
    ] != userUtils.getPP(
        userToken["user_id"],
        userToken["game_mode"],
        userToken["relax"],
        userToken["autopilot"],
    ):
        should_update_cached_stats = True

    if userToken["game_mode"] != packetData["gameMode"]:
        userToken["game_mode"] = packetData["gameMode"]
        should_update_cached_stats = True

    osuToken.update_token(
        userToken["token_id"],
        relax=userToken["relax"],
        autopilot=userToken["autopilot"],
        game_mode=userToken["game_mode"],
        # always update these
        action_id=packetData["actionID"],
        action_text=packetData["actionText"],
        action_md5=packetData["actionMd5"],
        action_mods=packetData["actionMods"],
        beatmap_id=packetData["beatmapID"],
    )
    if should_update_cached_stats:
        osuToken.updateCachedStats(userToken["token_id"])

    # Enqueue our new user panel and stats to us and our spectators
    recipients = [userToken]
    spectators = osuToken.get_spectators(userToken["token_id"])
    for spectator_user_id in spectators:
        token = osuToken.get_token_by_user_id(spectator_user_id)
        if token is not None:
            recipients.append(token)

    for spectator in recipients:
        # Force our own packet
        force = spectator == userToken

        osuToken.enqueue(
            spectator["token_id"],
            serverPackets.userPanel(userToken["user_id"], force),
        )
        osuToken.enqueue(
            spectator["token_id"],
            serverPackets.userStats(userToken["user_id"], force),
        )
