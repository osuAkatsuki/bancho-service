from __future__ import annotations

from common.constants import actions
from common.constants import mods
from common.ripple import user_utils
from constants import clientPackets
from constants import serverPackets
from objects import osuToken
from objects.osuToken import Token


async def handle(userToken: Token, rawPacketData: bytes) -> None:
    # Make sure we are not banned
    # if await user_utils.isBanned(userID):
    # 	userToken.enqueue(serverPackets.loginBanned)
    # 	return

    # Send restricted message if needed
    # if userToken["restricted"]:
    # 	await userToken.checkRestricted(True)

    # Change action packet
    packetData = clientPackets.userActionChange(rawPacketData)

    """ If we are not in spectate status but we're spectating someone, stop spectating
    if userToken.spectating != 0 and userToken.actionID != actions.WATCHING and userToken.actionID != actions.IDLE and userToken.actionID != actions.AFK:
        userToken.stopSpectating()

    # If we are not in multiplayer but we are in a match, part match
    if userToken.matchID != -1 and userToken.actionID != actions.MULTIPLAYING and userToken.actionID != actions.MULTIPLAYER and userToken.actionID != actions.AFK:
        userToken.partMatch()
    """

    relax_in_mods = packetData["actionMods"] & mods.RELAX != 0
    autopilot_in_mods = packetData["actionMods"] & mods.AUTOPILOT != 0

    # Update cached stats if relax/autopilot status changed
    should_update_cached_stats = False

    if relax_in_mods != userToken["relax"]:
        userToken["relax"] = relax_in_mods
        should_update_cached_stats = True

    if autopilot_in_mods != userToken["autopilot"]:
        userToken["autopilot"] = autopilot_in_mods
        should_update_cached_stats = True

    # Update cached stats if our pp changed if we've just submitted a score or we've changed gameMode
    user_pp = await user_utils.get_user_pp_for_mode(
        userToken["user_id"],
        userToken["game_mode"],
        userToken["relax"],
        userToken["autopilot"],
    )

    if (
        userToken["action_id"] in {actions.PLAYING, actions.MULTIPLAYING}
        or userToken["pp"] != user_pp
    ):
        should_update_cached_stats = True

    if userToken["game_mode"] != packetData["gameMode"]:
        userToken["game_mode"] = packetData["gameMode"]
        should_update_cached_stats = True

    # prevents possible crashes on getUserStats where AP is enabled and game_mode != 0
    if autopilot_in_mods and userToken["game_mode"] != 0:
        packetData["actionMods"] &= ~mods.AUTOPILOT
        should_update_cached_stats = True

    # prevents possible crashes on getUserStats where RX is enabled and game_mode is mania
    if relax_in_mods and userToken["game_mode"] == 3:
        packetData["actionMods"] &= ~mods.RELAX
        should_update_cached_stats = True

    await osuToken.update_token(
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
        await osuToken.updateCachedStats(userToken["token_id"])

    # Enqueue our new user panel and stats to us and our spectators
    recipients = [userToken]
    spectators = await osuToken.get_spectators(userToken["token_id"])
    for spectator_user_id in spectators:
        token = await osuToken.get_primary_token_by_user_id(spectator_user_id)
        if token is not None:
            recipients.append(token)

    for spectator in recipients:
        # Force our own packet
        force = spectator == userToken

        await osuToken.enqueue(
            spectator["token_id"],
            await serverPackets.userPanel(userToken["user_id"], force),
        )
        await osuToken.enqueue(
            spectator["token_id"],
            await serverPackets.userStats(userToken["user_id"], force),
        )
