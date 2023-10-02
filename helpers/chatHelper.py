from __future__ import annotations

from typing import TYPE_CHECKING

import settings
from common.constants import mods
from common.constants import privileges
from common.log import logger
from common.log import rap_logs
from common.ripple import userUtils
from constants import exceptions
from constants import serverPackets
from events import logoutEvent
from objects import channelList
from objects import fokabot
from objects import glob
from objects import osuToken
from objects import stream
from objects import streamList
from objects import tokenList
from objects.redisLock import redisLock

if TYPE_CHECKING:
    from typing import Optional


async def joinChannel(
    user_id: int = 0,
    channel_name: str = "",
    token_id: Optional[str] = None,
    toIRC: bool = True,
    force: bool = False,
) -> int:
    """
    Join a channel

    :param userID: user ID of the user that joins the channel. Optional. token can be used instead.
    :param token: user token object of user that joins the channel. Optional. userID can be used instead.
    :param channel: channel name
    :param toIRC: if True, send this channel join event to IRC. Must be true if joining from bancho. Default: True
    :param force: whether to allow game clients to join #spect_ and #multi_ channels
    :return: 0 if joined or other IRC code in case of error. Needed only on IRC-side
    """
    token: Optional[osuToken.Token] = None

    try:
        # Get token if not defined
        if token_id is None:
            token = await tokenList.getTokenFromUserID(user_id)
            # Make sure the token exists
            if token is None:
                raise exceptions.userNotFoundException
        else:
            token = await osuToken.get_token(token_id)
            if token is None:
                raise exceptions.userNotFoundException

        # Normal channel, do check stuff
        # Make sure the channel exists
        if channel_name not in await channelList.getChannelNames():
            raise exceptions.channelUnknownException()

        # Make sure a game client is not trying to join a #multi_ or #spect_ channel manually
        channel = await channelList.getChannel(channel_name)
        if channel is None:
            raise exceptions.channelUnknownException()

        if channel["instance"] and not token["irc"] and not force:
            raise exceptions.channelUnknownException()

        # Add the channel to our joined channel
        await osuToken.joinChannel(token["token_id"], channel_name)

        # Send channel joined (IRC)
        if settings.IRC_ENABLE and not toIRC:
            glob.ircServer.banchoJoinChannel(token["username"], channel_name)

        # Console output
        # logger.info(
        #     "User joined public chat channel",
        #     extra={
        #         "username": token["username"],
        #         "user_id": token["user_id"],
        #         "channel_name": channel,
        #     },
        # )

        # IRC code return
        return 0
    except exceptions.channelNoPermissionsException:
        assert token is not None
        logger.warning(
            "User attempted to join a channel they have no read permissions",
            extra={
                "username": token["username"],
                "user_id": token["user_id"],
                "channel_name": channel_name,
            },
        )
        return 403
    except exceptions.channelUnknownException:
        assert token is not None
        logger.warning(
            "User attempted to join an unknown channel",
            extra={
                "username": token["username"],
                "user_id": token["user_id"],
                "channel_name": channel_name,
            },
        )
        return 403
    except exceptions.userAlreadyInChannelException:
        assert token is not None
        logger.warning(
            "User attempted to join a channel they are already in",
            extra={
                "username": token["username"],
                "user_id": token["user_id"],
                "channel_name": channel_name,
            },
        )
        return 403
    except exceptions.userNotFoundException:
        logger.warning("User not connected to IRC/Bancho.")
        return 403  # idk


async def partChannel(
    userID: int = 0,
    channel_name: str = "",
    token_id: Optional[str] = None,
    toIRC: bool = True,
    kick: bool = False,
    force: bool = False,
) -> int:
    """
    Part a channel

    :param userID: user ID of the user that parts the channel. Optional. token can be used instead.
    :param token: user token object of user that parts the channel. Optional. userID can be used instead.
    :param channel: channel name
    :param toIRC: if True, send this channel join event to IRC. Must be true if joining from bancho. Optional. Default: True
    :param kick: if True, channel tab will be closed on client. Used when leaving lobby. Optional. Default: False
    :param force: whether to allow game clients to part #spect_ and #multi_ channels
    :return: 0 if joined or other IRC code in case of error. Needed only on IRC-side
    """
    token: Optional[osuToken.Token] = None

    try:
        # Make sure the client is not drunk and sends partChannel when closing a PM tab
        if not channel_name.startswith("#"):
            return 0

        # Get token if not defined
        if token_id is None:
            token = await tokenList.getTokenFromUserID(userID)
            # Make sure the token exists
            if token is None:
                raise exceptions.userNotFoundException()
        else:
            token = await osuToken.get_token(token_id)
            if token is None:
                raise exceptions.userNotFoundException

        # Determine internal/client name if needed
        # (toclient is used clientwise for #multiplayer and #spectator channels)
        channelClient = channel_name
        if channel_name == "#spectator":
            if token["spectating_user_id"] is None:
                spectating_user_id = userID
            else:
                spectating_user_id = token["spectating_user_id"]
            channel_name = f"#spect_{spectating_user_id}"
        elif channel_name == "#multiplayer":
            channel_name = f"#multi_{token['match_id']}"
        elif channel_name.startswith("#spect_"):
            channelClient = "#spectator"
        elif channel_name.startswith("#multi_"):
            channelClient = "#multiplayer"

        # Make sure the channel exists
        if channel_name not in await channelList.getChannelNames():
            raise exceptions.channelUnknownException()

        # Make sure a game client is not trying to join a #multi_ or #spect_ channel manually
        channel = await channelList.getChannel(channel_name)
        if channel is None:
            raise exceptions.channelUnknownException()

        if channel["instance"] and not token["irc"] and not force:
            raise exceptions.channelUnknownException()

        # Part channel (token-side and channel-side)
        await osuToken.partChannel(token["token_id"], channel_name)

        # Delete temporary channel if everyone left
        key = f"chat/{channel_name}"
        if key in await streamList.getStreams():
            if channel["instance"] and (await stream.getClientCount(key)) - 1 == 0:
                await channelList.removeChannel(channel_name)

        # Force close tab if needed
        # NOTE: Maybe always needed, will check later
        if kick:
            await osuToken.enqueue(
                token["token_id"],
                serverPackets.channelKicked(channelClient),
            )

        # IRC part
        if settings.IRC_ENABLE and toIRC:
            glob.ircServer.banchoPartChannel(token["username"], channel_name)

        # Console output
        # logger.info(
        #     "User left public chat channel",
        #     extra={
        #         "username": token["username"],
        #         "user_id": token["user_id"],
        #         "channel_name": channel,
        #     },
        # )

        # Return IRC code
        return 0
    except exceptions.channelUnknownException:
        assert token is not None
        logger.warning(
            "User attempted to leave a channel that does not exist",
            extra={
                "username": token["username"],
                "user_id": token["user_id"],
                "channel_name": channel_name,
            },
        )
        return 403
    except exceptions.userNotInChannelException:
        assert token is not None
        logger.warning(
            "User attempted to leave a channel they are not in",
            extra={
                "username": token["username"],
                "user_id": token["user_id"],
                "channel_name": channel_name,
            },
        )
        return 442
    except exceptions.userNotFoundException:
        logger.warning("User not connected to IRC/Bancho.")
        return 442  # idk


gamer_ids = [
    [99, 104, 101, 97, 116, 32],
    [99, 104, 101, 97, 116, 105, 110, 103],
    [97, 113, 110],
    [97, 113, 117, 105, 108, 97],
    [32, 104, 113],
    [97, 105, 110, 117],
    [109, 117, 108, 116, 105, 97, 99, 99],
    [109, 112, 103, 104],
    [107, 97, 119, 97, 116, 97],
    [104, 97, 99, 107],
    [109, 97, 112, 108, 101],
]


async def sendMessage(
    fro: Optional[str] = "",
    to: str = "",
    message: str = "",
    token_id: Optional[str] = None,
    toIRC: bool = True,
) -> int:
    """
    Send a message to osu!bancho and IRC server

    :param fro: sender username. Optional. token can be used instead
    :param to: receiver channel (if starts with #) or username
    :param message: text of the message
    :param token: sender token object. Optional. fro can be used instead
    :param toIRC: if True, send the message to IRC. If False, send it to Bancho only. Default: True
    :return: 0 if joined or other IRC code in case of error. Needed only on IRC-side
    """
    userToken: Optional[osuToken.Token] = None

    try:
        if token_id is None:
            userToken = await tokenList.getTokenFromUsername(fro)
            if userToken is None:
                raise exceptions.userNotFoundException()
        else:
            userToken = await osuToken.get_token(token_id)
            if userToken is None:
                raise exceptions.userNotFoundException()
            fro = userToken["username"]

        # Make sure this is not a tournament client
        if userToken["tournament"]:
            raise exceptions.userTournamentException()

        # Make sure the user is not in restricted mode
        if osuToken.is_restricted(userToken["privileges"]):
            raise exceptions.userRestrictedException()

        # Make sure the user is not silenced
        if await osuToken.isSilenced(userToken["token_id"]):
            raise exceptions.userSilencedException()

        # Redirect !report to FokaBot
        if message.startswith("!report"):
            to = glob.BOT_NAME

        # Determine internal name if needed
        # (toclient is used clientwise for #multiplayer and #spectator channels)
        toClient = to
        if to == "#spectator":
            if userToken["spectating_user_id"] is None:
                s = userToken["user_id"]
            else:
                s = userToken["spectating_user_id"]
            to = f"#spect_{s}"
        elif to == "#multiplayer":
            to = f"#multi_{userToken['match_id']}"
        elif to.startswith("#spect_"):
            toClient = "#spectator"
        elif to.startswith("#multi_"):
            toClient = "#multiplayer"

        isChannel = to[0] == "#"

        # Make sure the message is valid
        if not message.strip():
            raise exceptions.invalidArgumentsException()

        # Truncate really long messages
        if len(message) > 1024:
            message = f"{message[:1024]}... (truncated)"

        action_msg = message.startswith("\x01ACTION")

        # Send the message
        if isChannel:
            # CHANNEL
            # Make sure the channel exists
            channel = await channelList.getChannel(to)
            if channel is None:
                raise exceptions.channelUnknownException()

            # Make sure the channel is not in moderated mode
            if channel["moderated"] and not osuToken.is_staff(userToken["privileges"]):
                raise exceptions.channelModeratedException()

            # Make sure we are in the channel
            if to not in await osuToken.get_joined_channels(token_id):
                # I'm too lazy to put and test the correct IRC error code here...
                # but IRC is not strict at all so who cares
                raise exceptions.userNotInChannelException()

            # Make sure we have write permissions.

            # premium requires premium
            if (
                to == "#premium"
                and userToken["privileges"] & privileges.USER_PREMIUM == 0
            ):
                raise exceptions.channelNoPermissionsException()

            # supporter requires supporter
            if (
                to == "#supporter"
                and userToken["privileges"] & privileges.USER_DONOR == 0
            ):
                raise exceptions.channelNoPermissionsException()

            # non-public channels (except multiplayer) require staff or bot
            if (
                not channel["public_write"]
                and not (to.startswith("#multi_") or to.startswith("#spect_"))
            ) and not (
                osuToken.is_staff(userToken["privileges"])
                or userToken["user_id"] == 999
            ):
                raise exceptions.channelNoPermissionsException()

            # Check message for commands
            if not action_msg:
                fokaMessage = await fokabot.fokabotResponse(
                    userToken["username"],
                    to,
                    message,
                )
            else:
                fokaMessage = None

                # check for /np (rly bad lol)
                npmsg = " ".join(message.split(" ")[2:])

                match = fokabot.NOW_PLAYING_REGEX.match(npmsg)

                if match is None:  # should always match?
                    logger.error(
                        "Error parsing /np message",
                        extra={"chat_message": npmsg},
                    )
                    return "An error occurred while parsing /np message :/ - reported to devs"

                mods_int = 0
                if match["mods"] is not None:
                    for _mods in match["mods"][1:].split(" "):
                        mods_int |= mods.NP_MAPPING_TO_INTS[_mods]

                # Get beatmap id from URL
                beatmap_id = int(match["bid"])

                # Return tillerino message
                userToken = await osuToken.update_token(
                    token_id,
                    last_np={
                        "beatmap_id": beatmap_id,
                        "mods": mods_int,
                        "accuracy": -1.0,
                    },
                )
                assert userToken is not None

            msg_packet = serverPackets.sendMessage(
                fro=userToken["username"],
                to=toClient,
                message=message,
                fro_id=userToken["user_id"],
            )

            if fokaMessage:
                if fokaMessage["hidden"]:  # Send to user & gmt+
                    send_to = {
                        t["token_id"]
                        for t in await osuToken.get_tokens()  # TODO: use redis
                        if t["token_id"] != token_id
                        and osuToken.is_staff(t["privileges"])
                        and t["user_id"] != 999
                    }

                    # Send their command
                    await streamList.broadcast_limited(
                        f"chat/{to}",
                        msg_packet,
                        send_to,
                    )

                    # Send Aika's response
                    send_to.add(userToken["token_id"])
                    response_packet = serverPackets.sendMessage(
                        fro=glob.BOT_NAME,
                        to=toClient,
                        message=fokaMessage["response"],
                        fro_id=999,
                    )
                    await streamList.broadcast_limited(
                        f"chat/{to}",
                        response_packet,
                        send_to,
                    )
                else:  # Send to all streams
                    await osuToken.addMessageInBuffer(token_id, to, message)
                    await streamList.broadcast(
                        f"chat/{to}",
                        msg_packet,
                        but=[userToken["token_id"]],
                    )

                    aika_token = await tokenList.getTokenFromUserID(999)
                    assert aika_token is not None
                    await sendMessage(
                        token_id=aika_token["token_id"],
                        to=to,
                        message=fokaMessage["response"],
                    )
            else:
                await osuToken.addMessageInBuffer(token_id, to, message)
                await streamList.broadcast(
                    f"chat/{to}",
                    msg_packet,
                    but=[userToken["token_id"]],
                )
        else:
            # USER
            # Make sure recipient user is connected
            recipient_token = await tokenList.getTokenFromUsername(to)
            if recipient_token is None:
                raise exceptions.userNotFoundException()

            # Make sure the recipient is not a tournament client
            if recipient_token["tournament"]:
                raise exceptions.userTournamentException()

            # Notify the sender that the recipient is silenced.
            if await osuToken.isSilenced(recipient_token["token_id"]):
                await osuToken.enqueue(
                    recipient_token["token_id"],
                    serverPackets.targetSilenced(
                        to=to,
                        fro=userToken["username"],
                        fro_id=userToken["user_id"],
                    ),
                )

            if userToken["username"] != glob.BOT_NAME:
                # Make sure the recipient is not restricted or we are bot
                if osuToken.is_restricted(recipient_token["privileges"]):
                    raise exceptions.userRestrictedException()

                # TODO: Make sure the recipient has not disabled PMs for non-friends or he's our friend
                if recipient_token["block_non_friends_dm"] and userToken[
                    "user_id"
                ] not in await userUtils.getFriendList(recipient_token["user_id"]):
                    await osuToken.enqueue(
                        token_id,
                        serverPackets.targetBlockingDMs(
                            to=to,
                            fro=userToken["username"],
                            fro_id=userToken["user_id"],
                        ),
                    )
                    raise exceptions.userBlockingDMsException

            # Away check
            if await osuToken.awayCheck(
                recipient_token["token_id"],
                userToken["user_id"],
            ):
                await sendMessage(
                    fro=to,
                    to=fro,
                    message=f"\x01ACTION is away: {recipient_token['away_message'] or ''}\x01",
                )

            if to == glob.BOT_NAME:
                # Check message for commands
                fokaMessage = await fokabot.fokabotResponse(
                    userToken["username"],
                    to,
                    message,
                )

                if fokaMessage:
                    aika_token = await tokenList.getTokenFromUserID(999)
                    assert aika_token is not None
                    await sendMessage(
                        token_id=aika_token["token_id"],
                        to=fro,
                        message=fokaMessage["response"],
                    )
            else:
                packet = serverPackets.sendMessage(
                    fro=userToken["username"],
                    to=toClient,
                    message=message,
                    fro_id=userToken["user_id"],
                )
                await osuToken.enqueue(recipient_token["token_id"], packet)

        # Spam protection (ignore staff)
        if not osuToken.is_staff(userToken["privileges"]):
            await osuToken.spamProtection(token_id)

        if (
            any([bytes(gid).decode() in message for gid in gamer_ids])
            and not action_msg
            and not osuToken.is_staff(userToken["privileges"])
        ):
            webhook_channel = "ac_confidential"
        else:
            webhook_channel = None

        if isChannel:
            if webhook_channel:
                await rap_logs.send_rap_log_as_discord_webhook(
                    message=f"{osuToken.getMessagesBufferString(token_id)}",
                    discord_channel=webhook_channel,
                )
            else:
                logger.info(
                    "User sent a chat message",
                    extra={
                        "sender": userToken["username"],
                        "recipeint": to,
                        "chat_message": message,
                    },
                )
        else:
            if webhook_channel:
                await rap_logs.send_rap_log_as_discord_webhook(
                    message=f"{fro} @ {to}: {message}",
                    discord_channel=webhook_channel,
                )

        return 0
    except exceptions.userSilencedException:
        silence_time_left = await osuToken.getSilenceSecondsLeft(token_id)
        await osuToken.enqueue(
            token_id,
            serverPackets.silenceEndTime(silence_time_left),
        )
        logger.warning(
            "User tried to send a message during silence",
            extra={
                "username": userToken["username"],
                "user_id": userToken["user_id"],
            },
        )
        return 404
    except exceptions.userNotInChannelException:
        logger.warning(
            "User tried to send a message to a channel they are not in",
            extra={
                "username": userToken["username"],
                "user_id": userToken["user_id"],
                "channel_name": to,
            },
        )
        return 404
    except exceptions.channelModeratedException:
        logger.warning(
            "User tried to send a message to a moderated channel",
            extra={
                "username": userToken["username"],
                "user_id": userToken["user_id"],
                "channel_name": to,
            },
        )
        return 404
    except exceptions.channelUnknownException:
        logger.warning(
            "User tried to send a message to an unknown channel",
            extra={
                "username": userToken["username"],
                "user_id": userToken["user_id"],
                "channel_name": to,
            },
        )
        return 403
    except exceptions.channelNoPermissionsException:
        logger.warning(
            "User tried to send a message to a channel they have no write permissions",
            extra={
                "username": userToken["username"],
                "user_id": userToken["user_id"],
                "channel_name": to,
            },
        )
        return 404
    except exceptions.userRestrictedException:
        # TODO: this is kinda weird that we can't differentiate
        # between sender and recipient restricted here..
        logger.warning(
            "Sender or recipient in messaging interaction were restricted",
            extra={
                "username": userToken["username"],
                "user_id": userToken["user_id"],
                "recipient": to,
            },
        )
        return 404
    except exceptions.userTournamentException:
        logger.warning(
            "User tried to send a message to a tournament client",
            extra={
                "username": userToken["username"],
                "user_id": userToken["user_id"],
                "recipient": to,
            },
        )
        return 404
    except exceptions.userNotFoundException:
        logger.warning("User not connected to IRC/Bancho.")
        return 401
    except exceptions.userBlockingDMsException:
        logger.warning(
            "User tried to send a message to a user that is blocking non-friends dms",
            extra={
                "username": userToken["username"],
                "user_id": userToken["user_id"],
                "recipient": to,
            },
        )
        return 404
    except exceptions.invalidArgumentsException:
        logger.warning(
            "User tried to send an invalid message",
            extra={
                "username": userToken["username"],
                "user_id": userToken["user_id"],
                "recipient": to,
            },
        )
        return 404
    except:
        logger.exception("An unhandled exception occurred whle sending a chat message")


""" IRC-Bancho Connect/Disconnect/Join/Part interfaces"""


async def fixUsernameForBancho(username: str) -> str:
    """
    Convert username from IRC format (without spaces) to Bancho format (with spaces)

    :param username: username to convert
    :return: converted username
    """
    # If there are no spaces or underscores in the name
    # return it
    if not (" " in username and "_" in username):
        return username

    # Exact match first
    result = await glob.db.fetch(
        "SELECT id " "FROM users " "WHERE username = %s LIMIT 1",
        [username],
    )
    if result:
        return username

    # Username not found, replace _ with space
    return username.replace("_", " ")


def fixUsernameForIRC(username: str) -> str:
    """
    Convert an username from Bancho format to IRC format (underscores instead of spaces)

    :param username: username to convert
    :return: converted username
    """
    return username.replace(" ", "_")


async def IRCConnect(username: str) -> None:
    """
    Handle IRC login bancho-side.
    Add token and broadcast login packet.

    :param username: username
    :return:
    """
    user_id = await userUtils.getID(username)
    if not user_id:
        return

    async with redisLock("bancho:locks:tokens"):
        await tokenList.deleteOldTokens(user_id)
        await tokenList.addToken(user_id, irc=True)

    await streamList.broadcast("main", await serverPackets.userPanel(user_id))
    logger.info("User logged into IRC", extra={"username": username})


async def IRCDisconnect(username: str) -> None:
    """
    Handle IRC logout bancho-side.
    Remove token and broadcast logout packet.

    :param username: username
    :return:
    """
    token = await osuToken.get_token_by_username(username)
    if token is None:
        return

    await logoutEvent.handle(token)  # TODO
    logger.info("User logged out of IRC", extra={"username": username})


async def IRCJoinChannel(username: str, channel: str) -> Optional[int]:
    """
    Handle IRC channel join bancho-side.

    :param username: username
    :param channel: channel name
    :return: IRC return code
    """
    userID = await userUtils.getID(username)
    if not userID:
        logger.warning(
            "User not found by name when attempting to join channel",
            extra={"username": username},
        )
        return

    # NOTE: This should have also `toIRC` = False` tho,
    # since we send JOIN message later on ircserver.py.
    # Will test this later
    return await joinChannel(userID, channel)


async def IRCPartChannel(username: str, channel: str) -> Optional[int]:
    """
    Handle IRC channel part bancho-side.

    :param username: username
    :param channel: channel name
    :return: IRC return code
    """
    userID = await userUtils.getID(username)
    if not userID:
        logger.warning(
            "User not found by name when attempting to leave channel",
            extra={"username": username},
        )
        return

    return await partChannel(userID, channel)


async def IRCAway(username: str, message: str) -> Optional[int]:
    """
    Handle IRC away command bancho-side.

    :param username:
    :param message: away message
    :return: IRC return code
    """
    userID = await userUtils.getID(username)
    if not userID:
        logger.warning(
            "User not found by name when attempting to handle the AWAY command",
            extra={"username": username},
        )
        return  # TODO: should this be returning a code?

    token = await osuToken.get_token_by_user_id(userID)
    if token is None:
        logger.warning(
            "User session not found by name when attempting to handle the AWAY command",
            extra={"username": username, "user_id": userID},
        )
        return

    await osuToken.update_token(
        token["token_id"],
        away_message=message,
    )
    return 306 if message else 305
