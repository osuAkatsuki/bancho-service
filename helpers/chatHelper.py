from __future__ import annotations

from typing import TYPE_CHECKING

from common.constants import mods
from common.constants import privileges
from common.log import audit_logs
from common.log import logger
from common.ripple import user_utils
from constants import CHATBOT_USER_ID
from constants import exceptions
from constants import serverPackets
from objects import channelList
from objects import chatbot
from objects import glob
from objects import osuToken
from objects import stream
from objects import streamList
from objects import tokenList

if TYPE_CHECKING:
    from typing import Optional


async def join_channel(
    channel_name: str,
    token_id: str,
    *,
    allow_instance_channels: bool = False,
) -> None:
    """
    Join a channel

    :param token: user token object of user that joins the channel.
    :param channel: channel name
    :param allow_instance_channels: whether to allow game clients to join #spect_ and #mp_ channels
    :return: None
    """
    token: Optional[osuToken.Token] = None

    try:
        token = await osuToken.get_token(token_id)
        if token is None:
            raise exceptions.userNotFoundException

        # Make sure a game client is not trying to join a #mp_ or #spect_ channel manually
        channel = await channelList.getChannel(channel_name)
        if channel is None or (channel["instance"] and not allow_instance_channels):
            raise exceptions.channelUnknownException()

        # Add the channel to our joined channel
        await osuToken.joinChannel(token["token_id"], channel_name)

        return None
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
        return None
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
        return None
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
        return None
    except exceptions.userNotFoundException:
        logger.warning("User not connected to Bancho.")
        return None


async def part_channel(
    channel_name: str,
    token_id: str,
    *,
    notify_user_of_kick: bool = False,
    allow_instance_channels: bool = False,
) -> None:
    """
    Part a channel

    :param channel: channel name
    :param token_id: user token object of user that parts the channel.
    :param notify_user_of_kick: if True, channel tab will be closed on client. Used when leaving lobby.
    :param allow_instance_channels: whether to allow game clients to part #spect_ and #mp_ channels
    :return: None
    """
    token: Optional[osuToken.Token] = None

    try:
        # Make sure the client is not drunk and sends partChannel when closing a PM tab
        if not channel_name.startswith("#"):
            return None

        token = await osuToken.get_token(token_id)
        if token is None:
            raise exceptions.userNotFoundException

        # Determine internal/client name if needed
        # (toclient is used clientwise for #multiplayer and #spectator channels)
        channelClient = channel_name
        if channel_name == "#spectator":
            if token["spectating_user_id"] is None:
                raise exceptions.channelUnknownException()

            spectating_user_id = token["spectating_user_id"]
            channel_name = f"#spect_{spectating_user_id}"
        elif channel_name == "#multiplayer":
            channel_name = f"#mp_{token['match_id']}"
        elif channel_name.startswith("#spect_"):
            channelClient = "#spectator"
        elif channel_name.startswith("#mp_"):
            channelClient = "#multiplayer"

        # Make sure the channel exists
        if channel_name not in await channelList.getChannelNames():
            raise exceptions.channelUnknownException()

        # Make sure a game client is not trying to join a #mp_ or #spect_ channel manually
        channel = await channelList.getChannel(channel_name)
        if channel is None:
            raise exceptions.channelUnknownException()

        if channel["instance"] and not allow_instance_channels:
            raise exceptions.channelUnknownException()

        # Part channel (token-side and channel-side)
        await osuToken.partChannel(token["token_id"], channel_name)

        # Delete temporary channel if everyone left
        key = f"chat/{channel_name}"
        if key in await streamList.getStreams():
            if channel["instance"] and (await stream.get_client_count(key)) - 1 == 0:
                await channelList.removeChannel(channel_name)

        # Force close tab if needed
        # NOTE: Maybe always needed, will check later
        if notify_user_of_kick:
            await osuToken.enqueue(
                token["token_id"],
                serverPackets.channelKicked(channelClient),
            )

        return None
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
        return None
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
        return None
    except exceptions.userNotFoundException:
        logger.warning("User not connected to Bancho.")
        return None


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


async def send_message(
    recipient_name: str,
    message: str,
    sender_token_id: str,
) -> None:
    """
    Send a message to osu!bancho

    :param recipient_name: receiver channel (if starts with #) or username
    :param message: text of the message
    :param sender_token_id: sender token object.
    :return: None
    """
    userToken: Optional[osuToken.Token] = None

    try:
        userToken = await osuToken.get_token(sender_token_id)
        if userToken is None:
            raise exceptions.userNotFoundException()

        # Make sure this is not a tournament client
        if userToken["tournament"]:
            raise exceptions.userTournamentException()

        # Make sure the user is not in restricted mode
        if osuToken.is_restricted(userToken["privileges"]):
            raise exceptions.userRestrictedException()

        # Make sure the user is not silenced
        if await osuToken.isSilenced(userToken["token_id"]):
            raise exceptions.userSilencedException()

        # Redirect !report to chatbot
        if message.startswith("!report"):
            recipient_name = glob.BOT_NAME

        # Determine internal name if needed
        # (toclient is used clientwise for #multiplayer and #spectator channels)
        toClient = recipient_name
        if recipient_name == "#spectator":
            if userToken["spectating_user_id"] is None:
                s = userToken["user_id"]
            else:
                s = userToken["spectating_user_id"]
            recipient_name = f"#spect_{s}"
        elif recipient_name == "#multiplayer":
            recipient_name = f"#mp_{userToken['match_id']}"
        elif recipient_name.startswith("#spect_"):
            toClient = "#spectator"
        elif recipient_name.startswith("#mp_"):
            toClient = "#multiplayer"

        isChannel = recipient_name[0] == "#"

        # Make sure the message is valid
        if not message.strip():
            raise exceptions.invalidArgumentsException()

        # Truncate really long messages
        if len(message) > 1024 and userToken["user_id"] != CHATBOT_USER_ID:
            message = f"{message[:1024]}... (truncated)"

        action_msg = message.startswith("\x01ACTION")

        # Send the message
        if isChannel:
            # CHANNEL
            # Make sure the channel exists
            channel = await channelList.getChannel(recipient_name)
            if channel is None:
                raise exceptions.channelUnknownException()

            # Make sure the channel is not in moderated mode
            if channel["moderated"] and not osuToken.is_staff(userToken["privileges"]):
                raise exceptions.channelModeratedException()

            # Make sure we are in the channel
            if recipient_name not in await osuToken.get_joined_channels(
                userToken["token_id"],
            ):
                raise exceptions.userNotInChannelException()

            # Make sure we have write permissions.

            # premium requires premium
            if (
                recipient_name == "#premium"
                and userToken["privileges"] & privileges.USER_PREMIUM == 0
            ):
                raise exceptions.channelNoPermissionsException()

            # supporter requires supporter
            if (
                recipient_name == "#supporter"
                and userToken["privileges"] & privileges.USER_DONOR == 0
            ):
                raise exceptions.channelNoPermissionsException()

            # non-public channels (except multiplayer) require staff or bot
            if (
                not channel["public_write"]
                and not (
                    recipient_name.startswith("#mp_")
                    or recipient_name.startswith("#spect_")
                )
            ) and not (
                osuToken.is_staff(userToken["privileges"])
                or userToken["user_id"] == CHATBOT_USER_ID
            ):
                raise exceptions.channelNoPermissionsException()

            # Check message for commands
            if not action_msg:
                chatbot_response = await chatbot.query(
                    userToken["username"],
                    recipient_name,
                    message,
                )
            else:
                chatbot_response = None

                # check for /np (rly bad lol)
                npmsg = " ".join(message.split(" ")[2:])

                match = chatbot.NOW_PLAYING_REGEX.match(npmsg)

                if match is None:  # should always match?
                    logger.error(
                        "Error parsing /np message",
                        extra={"chat_message": npmsg},
                    )
                    return None

                mods_int = 0
                if match["mods"] is not None:
                    for _mods in match["mods"][1:].split(" "):
                        mods_int |= mods.NP_MAPPING_TO_INTS[_mods]

                # Get beatmap id from URL
                beatmap_id = int(match["bid"])

                # Return tillerino message
                userToken = await osuToken.update_token(
                    userToken["token_id"],
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

            if chatbot_response:
                logger.info(
                    "Chatbot interaction",
                    extra={
                        "username": userToken["username"],
                        "user_id": userToken["user_id"],
                        "channel_name": recipient_name,
                        "user_message": message,
                        "chatbot_response": chatbot_response,
                    },
                )

                if chatbot_response["hidden"]:  # Send to user & gmt+
                    send_to = {
                        t["token_id"]
                        for t in await osuToken.get_tokens()  # TODO: use redis
                        if (
                            t["token_id"] != userToken["token_id"]
                            and osuToken.is_staff(t["privileges"])
                            and t["user_id"] != CHATBOT_USER_ID
                        )
                    }

                    # Send their command
                    await streamList.multicast(
                        f"chat/{recipient_name}",
                        msg_packet,
                        send_to,
                    )

                    # Send Aika's response
                    send_to.add(userToken["token_id"])
                    response_packet = serverPackets.sendMessage(
                        fro=glob.BOT_NAME,
                        to=toClient,
                        message=chatbot_response["response"],
                        fro_id=CHATBOT_USER_ID,
                    )
                    await streamList.multicast(
                        f"chat/{recipient_name}",
                        response_packet,
                        send_to,
                    )
                else:  # Send to all streams
                    await osuToken.addMessageInBuffer(
                        userToken["token_id"],
                        recipient_name,
                        message,
                    )
                    await streamList.broadcast(
                        f"chat/{recipient_name}",
                        msg_packet,
                        but=[userToken["token_id"]],
                    )

                    aika_token = await tokenList.getTokenFromUserID(CHATBOT_USER_ID)
                    assert aika_token is not None
                    await send_message(
                        sender_token_id=aika_token["token_id"],
                        recipient_name=recipient_name,
                        message=chatbot_response["response"],
                    )
            else:
                await osuToken.addMessageInBuffer(
                    userToken["token_id"],
                    recipient_name,
                    message,
                )
                await streamList.broadcast(
                    f"chat/{recipient_name}",
                    msg_packet,
                    but=[userToken["token_id"]],
                )
        else:
            # USER
            # Make sure recipient user is connected
            recipient_token = await tokenList.getTokenFromUsername(recipient_name)
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
                        to=recipient_name,
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
                ] not in await user_utils.get_friend_user_ids(
                    recipient_token["user_id"],
                ):
                    await osuToken.enqueue(
                        userToken["token_id"],
                        serverPackets.targetBlockingDMs(
                            to=recipient_name,
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
                await send_message(
                    recipient_name=userToken["username"],
                    sender_token_id=recipient_token["token_id"],
                    message=f"\x01ACTION is away: {recipient_token['away_message'] or ''}\x01",
                )

            if recipient_name == glob.BOT_NAME:
                # Check message for commands
                chatbot_response = await chatbot.query(
                    userToken["username"],
                    recipient_name,
                    message,
                )

                if chatbot_response:
                    chatbot_token = await tokenList.getTokenFromUserID(CHATBOT_USER_ID)
                    assert chatbot_token is not None
                    await send_message(
                        sender_token_id=chatbot_token["token_id"],
                        recipient_name=userToken["username"],
                        message=chatbot_response["response"],
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
            await osuToken.spamProtection(userToken["token_id"])

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
                await audit_logs.send_log_as_discord_webhook(
                    message=f"{await osuToken.getMessagesBufferString(userToken['token_id'])}",
                    discord_channel=webhook_channel,
                )
            else:
                logger.info(
                    "User sent a chat message",
                    extra={
                        "sender": userToken["username"],
                        "recipeint": recipient_name,
                        "chat_message": message,
                    },
                )
        else:
            if webhook_channel:
                await audit_logs.send_log_as_discord_webhook(
                    message=f"{userToken['username']} @ {recipient_name}: {message}",
                    discord_channel=webhook_channel,
                )

        return None
    except exceptions.userSilencedException:
        assert userToken is not None
        silence_time_left = await osuToken.getSilenceSecondsLeft(userToken["token_id"])
        await osuToken.enqueue(
            userToken["token_id"],
            serverPackets.silenceEndTime(silence_time_left),
        )
        logger.warning(
            "User tried to send a message during silence",
            extra={
                "username": userToken and userToken["username"],
                "user_id": userToken and userToken["user_id"],
            },
        )
        return None
    except exceptions.userNotInChannelException:
        logger.warning(
            "User tried to send a message to a channel they are not in",
            extra={
                "username": userToken and userToken["username"],
                "user_id": userToken and userToken["user_id"],
                "channel_name": recipient_name,
            },
        )
        return None
    except exceptions.channelModeratedException:
        logger.warning(
            "User tried to send a message to a moderated channel",
            extra={
                "username": userToken and userToken["username"],
                "user_id": userToken and userToken["user_id"],
                "channel_name": recipient_name,
            },
        )
        return None
    except exceptions.channelUnknownException:
        logger.warning(
            "User tried to send a message to an unknown channel",
            extra={
                "username": userToken and userToken["username"],
                "user_id": userToken and userToken["user_id"],
                "channel_name": recipient_name,
            },
        )
        return None
    except exceptions.channelNoPermissionsException:
        logger.warning(
            "User tried to send a message to a channel they have no write permissions",
            extra={
                "username": userToken and userToken["username"],
                "user_id": userToken and userToken["user_id"],
                "channel_name": recipient_name,
            },
        )
        return None
    except exceptions.userRestrictedException:
        # TODO: this is kinda weird that we can't differentiate
        # between sender and recipient restricted here..
        logger.warning(
            "Sender or recipient in messaging interaction were restricted",
            extra={
                "username": userToken and userToken["username"],
                "user_id": userToken and userToken["user_id"],
                "recipient": recipient_name,
            },
        )
        return None
    except exceptions.userTournamentException:
        logger.warning(
            "User tried to send a message to a tournament client",
            extra={
                "username": userToken and userToken["username"],
                "user_id": userToken and userToken["user_id"],
                "recipient": recipient_name,
            },
        )
        return None
    except exceptions.userNotFoundException:
        logger.warning("User not connected to Bancho.")
        return None
    except exceptions.userBlockingDMsException:
        logger.warning(
            "User tried to send a message to a user that is blocking non-friends dms",
            extra={
                "username": userToken and userToken["username"],
                "user_id": userToken and userToken["user_id"],
                "recipient": recipient_name,
            },
        )
        return None
    except exceptions.invalidArgumentsException:
        logger.warning(
            "User tried to send an invalid message",
            extra={
                "username": userToken and userToken["username"],
                "user_id": userToken and userToken["user_id"],
                "recipient": recipient_name,
            },
        )
        return None
    except:
        logger.exception("An unhandled exception occurred whle sending a chat message")
        return None
