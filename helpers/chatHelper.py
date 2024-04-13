from __future__ import annotations

from typing import TYPE_CHECKING

from common.constants import privileges
from common.log import audit_logs
from common.log import logger
from common.ripple import user_utils
from constants import CHATBOT_USER_ID
from constants import exceptions
from constants import serverPackets
from objects import channelList
from objects import chatbot
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


def _check_for_gamer_ids(message: str) -> bool:
    for gid in gamer_ids:
        if bytes(gid).decode() in message:
            return True

    return False


def _get_client_channel_and_channel(
    user_token: osuToken.Token,
    channel_name: str,
) -> tuple[str, str]:
    # Find the correct channel name
    client_channel_name = channel_name
    if channel_name == "#spectator":
        if user_token["spectating_user_id"] is None:
            spectating_user_id = user_token["user_id"]
        else:
            spectating_user_id = user_token["spectating_user_id"]
        channel_name = f"#spect_{spectating_user_id}"

    elif channel_name == "#multiplayer":
        channel_name = f"#multi_{user_token['match_id']}"

    elif channel_name.startswith("#spect_"):
        client_channel_name = "#spectator"

    elif channel_name.startswith("#multi_"):
        client_channel_name = "#multiplayer"

    return channel_name, client_channel_name


# TODO: add a functionality to handle sending to both IRC and bancho-service
async def enqueue_private_message(
    user_token: osuToken.Token,
    recipient_token: osuToken.Token,
    message: str,
) -> None:
    packet = serverPackets.sendMessage(
        fro=user_token["username"],
        to=recipient_token["username"],
        message=message,
        fro_id=user_token["user_id"],
    )
    await osuToken.enqueue(recipient_token["token_id"], packet)


async def enqueue_public_message(
    user_token: osuToken.Token,
    channel_name: str,
    client_channel_name: str,
    message: str,
    but: list[str] = [],
) -> None:
    packet = serverPackets.sendMessage(
        fro=user_token["username"],
        to=client_channel_name,
        message=message,
        fro_id=user_token["user_id"],
    )

    await streamList.broadcast(
        f"chat/{channel_name}",
        packet,
        but=but,
    )


async def enqueue_public_limited_message(
    user_token: osuToken.Token,
    channel_name: str,
    client_channel_name: str,
    message: str,
    send_to: list[str] = [],
) -> None:
    packet = serverPackets.sendMessage(
        fro=user_token["username"],
        to=client_channel_name,
        message=message,
        fro_id=user_token["user_id"],
    )

    await streamList.broadcast_limited(
        f"chat/{channel_name}",
        packet,
        send_to,
    )


async def handle_private_bot_response(
    user_token: osuToken.Token,
    response: Optional[chatbot.CommandResponse],
) -> None:
    if response is None:
        return

    aika_token = await tokenList.getTokenFromUserID(CHATBOT_USER_ID)
    assert aika_token is not None

    # chatbot's response
    await enqueue_private_message(
        user_token=aika_token,
        recipient_token=user_token,
        message=response["response"],
    )


async def handle_public_bot_response(
    user_token: osuToken.Token,
    send_to: str,
    message: str,
    response: Optional[chatbot.CommandResponse],
) -> None:
    channel_name, client_channel_name = _get_client_channel_and_channel(
        user_token=user_token,
        channel_name=send_to,
    )

    aika_token = await tokenList.getTokenFromUserID(CHATBOT_USER_ID)
    assert aika_token is not None

    # Response is only visible to user and some staff members
    if response is not None and response["hidden"]:
        enqueue_to = {  # I hate this part so much
            t["token_id"]
            for t in await osuToken.get_tokens()  # TODO: use redis
            if (
                t["token_id"] != user_token["token_id"]
                and osuToken.is_staff(t["privileges"])
                and t["user_id"] != CHATBOT_USER_ID
            )
        }

        # user's message
        await enqueue_public_limited_message(
            user_token=user_token,
            channel_name=channel_name,
            client_channel_name=client_channel_name,
            message=message,
            send_to=list(enqueue_to),
        )

        # chatbot's response
        enqueue_to.add(user_token["token_id"])
        await enqueue_public_limited_message(
            user_token=aika_token,
            channel_name=channel_name,
            client_channel_name=client_channel_name,
            message=response["response"],
            send_to=list(enqueue_to),
        )
        return

    # There are 2 cases here: no response from chatbot
    # or response from chatbot visible to everyone eg. !roll
    await osuToken.addMessageInBuffer(user_token["token_id"], channel_name, message)
    await enqueue_public_message(  # user's message
        user_token=user_token,
        channel_name=channel_name,
        client_channel_name=client_channel_name,
        message=message,
        but=[user_token["token_id"]],
    )

    if response is not None:  # chatbot's response
        await enqueue_public_message(
            user_token=aika_token,
            channel_name=channel_name,
            client_channel_name=client_channel_name,
            message=response["response"],
        )


async def handle_interaction_with_bot(
    user_token: osuToken.Token,
    send_to: str,
    message: str,
) -> Optional[int]:
    # This is a special case and we need to redirect it to chatbot's DM's
    if message.startswith("!report"):
        send_to = glob.BOT_NAME

    response = await chatbot.query(
        user_token["username"],
        send_to,
        message,
    )

    logger.info(
        "User triggered chatbot interaction",
        extra={
            "token_id": user_token["token_id"],
            "username": user_token["username"],
            "user_id": user_token["user_id"],
            "send_to": send_to,
        },
    )

    is_channel = send_to.startswith("#")
    if is_channel:
        await handle_public_bot_response(
            user_token=user_token,
            send_to=send_to,
            message=message,
            response=response,
        )
    else:
        await handle_private_bot_response(
            user_token=user_token,
            response=response,
        )


async def handle_public_message(
    user_token: osuToken.Token,
    send_to: str,
    message: str,
) -> Optional[int]:
    channel_name, client_channel_name = _get_client_channel_and_channel(
        user_token,
        send_to,
    )

    channel = await channelList.getChannel(channel_name)
    if channel is None:
        logger.warning(
            "User attempted to send a message to an unknown channel",
            extra={
                "token_id": user_token["token_id"],
                "username": user_token["username"],
                "user_id": user_token["user_id"],
                "channel_name": channel_name,
            },
        )

        return ...

    if channel["moderated"] and not osuToken.is_staff(user_token["privileges"]):
        logger.warning(
            "User attempted to send a message to a moderated channel",
            extra={
                "token_id": user_token["token_id"],
                "username": user_token["username"],
                "user_id": user_token["user_id"],
                "channel_name": channel_name,
            },
        )

        return ...

    if channel_name not in await osuToken.get_joined_channels(user_token["token_id"]):
        logger.warning(
            "User attempted to send a message to a channel they are not in",
            extra={
                "token_id": user_token["token_id"],
                "username": user_token["username"],
                "user_id": user_token["user_id"],
                "channel_name": channel_name,
            },
        )

        return ...

    if (
        channel_name == "#premium"
        and user_token["privileges"] & privileges.USER_PREMIUM == 0
    ):
        logger.warning(
            "User attempted to send a message to a premium channel without premium permissions",
            extra={
                "token_id": user_token["token_id"],
                "username": user_token["username"],
                "user_id": user_token["user_id"],
                "channel_name": channel_name,
            },
        )

        return ...

    if (
        channel_name == "#supporter"
        and user_token["privileges"] & privileges.USER_DONOR == 0
    ):
        logger.warning(
            "User attempted to send a message to a supporter channel without supporter permissions",
            extra={
                "token_id": user_token["token_id"],
                "username": user_token["username"],
                "user_id": user_token["user_id"],
                "channel_name": channel_name,
            },
        )

        return ...

    if (
        not channel["public_write"]
        and not (
            channel_name.startswith("#multi_") or channel_name.startswith("#spect_")
        )
        and not osuToken.is_staff(user_token["privileges"])
    ):
        logger.warning(
            "User attempted to send a message to a non-public channel without permissions",
            extra={
                "token_id": user_token["token_id"],
                "username": user_token["username"],
                "user_id": user_token["user_id"],
                "channel_name": channel_name,
            },
        )

        return ...

    await osuToken.addMessageInBuffer(user_token["token_id"], channel_name, message)
    await enqueue_public_message(
        user_token=user_token,
        channel_name=channel_name,
        client_channel_name=client_channel_name,
        message=message,
        but=[user_token["token_id"]],
    )


async def handle_private_message(
    user_token: osuToken.Token,
    send_to: str,
    message: str,
) -> Optional[int]:
    recipient_token = await tokenList.getTokenFromUsername(send_to)
    if recipient_token is None:
        logger.warning(
            "User attempted to send a message to an unknown user",
            extra={
                "token_id": user_token["token_id"],
                "username": user_token["username"],
                "user_id": user_token["user_id"],
                "recipient": send_to,
            },
        )
        return ...

    if recipient_token["tournament"]:
        logger.warning(
            "User attempted to send a message to a tournament client",
            extra={
                "token_id": user_token["token_id"],
                "username": user_token["username"],
                "user_id": user_token["user_id"],
                "recipient": send_to,
            },
        )
        return ...

    if await osuToken.isSilenced(recipient_token["token_id"]):
        await osuToken.enqueue(
            user_token["token_id"],
            serverPackets.targetSilenced(recipient_token["username"]),
        )

        logger.warning(
            "User tried to send a message to a silenced user",
            extra={
                "token_id": user_token["token_id"],
                "username": user_token["username"],
                "user_id": user_token["user_id"],
                "recipient_username": recipient_token["username"],
                "recipient_user_id": recipient_token["user_id"],
            },
        )

        return ...

    if osuToken.is_restricted(recipient_token["privileges"]):
        logger.warning(
            "User attempted to send a message to a restricted user",
            extra={
                "token_id": user_token["token_id"],
                "username": user_token["username"],
                "user_id": user_token["user_id"],
                "recipient_username": recipient_token["username"],
                "recipient_user_id": recipient_token["user_id"],
            },
        )
        return ...

    # TODO: check if user has us blacklisted
    # fmt: off
    if (
        recipient_token["block_non_friends_dm"]
        and (
            user_token["user_id"]
            not in await user_utils.get_friend_user_ids(recipient_token["user_id"])
        )
    ):
    # fmt: on
        await osuToken.enqueue(
            user_token["token_id"],
            serverPackets.targetBlockingDMs(recipient_token["username"]),
        )

        logger.warning(
            "User tried to send a message to a user that is blocking non-friends dms",
            extra={
                "token_id": user_token["token_id"],
                "username": user_token["username"],
                "user_id": user_token["user_id"],
                "recipient_username": recipient_token["username"],
                "recipient_user_id": recipient_token["user_id"],
            },
        )

        return ...

    if await osuToken.awayCheck(
        recipient_token["token_id"],
        user_token["user_id"],
    ):
        await enqueue_private_message(
            user_token=recipient_token,
            recipient_token=user_token,
            message=f"\x01ACTION is away: {recipient_token['away_message'] or ''}\x01",
        )

    await enqueue_private_message(
        user_token=user_token,
        recipient_token=recipient_token,
        message=message,
    )


async def handle_bot_message(
    user_token: osuToken.Token,
    send_to: str,
    message: str,
) -> Optional[int]:
    is_channel = send_to.startswith("#")

    if is_channel:
        channel_name, client_channel_name = _get_client_channel_and_channel(
            user_token,
            send_to,
        )

        channel = await channelList.getChannel(channel_name)
        if channel is None:
            logger.warning(
                "User attempted to send a message to an unknown channel",
                extra={
                    "token_id": user_token["token_id"],
                    "username": user_token["username"],
                    "user_id": user_token["user_id"],
                    "channel_name": channel_name,
                },
            )

            return ...

        await osuToken.addMessageInBuffer(user_token["token_id"], channel_name, message)
        await enqueue_public_message(
            user_token=user_token,
            channel_name=channel_name,
            client_channel_name=client_channel_name,
            message=message,
            but=[user_token["token_id"]],
        )

    else:
        recipient_token = await tokenList.getTokenFromUsername(send_to)
        if recipient_token is None:
            logger.warning(
                "User attempted to send a message to an unknown user",
                extra={
                    "token_id": user_token["token_id"],
                    "username": user_token["username"],
                    "user_id": user_token["user_id"],
                    "recipient": send_to,
                },
            )
            return ...

        await enqueue_private_message(
            user_token=user_token,
            recipient_token=recipient_token,
            message=message,
        )

    logger.info(
        "Chatbot sent a message",
        extra={
            "token_id": user_token["token_id"],
            "username": user_token["username"],
            "user_id": user_token["user_id"],
            "send_to": send_to,
        },
    )


async def sendMessage(
    token_id: str,
    send_to: str,
    message: str,
) -> Optional[int]:
    user_token = await osuToken.get_token(token_id)
    if user_token is None:
        logger.warning(
            "User tried to send message but they are not connected to server",
            extra={"token_id": token_id},
        )
        return ...  # TODO: return IRC codes

    if user_token["user_id"] == CHATBOT_USER_ID:
        return await handle_bot_message(
            user_token=user_token,
            send_to=send_to,
            message=message,
        )

    if user_token["tournament"]:
        logger.warning(
            "User tried to send message but they are connected from tournament client",
            extra={
                "token_id": token_id,
                "username": user_token["username"],
                "user_id": user_token["user_id"],
                "send_to": send_to,
            },
        )
        return ...

    if osuToken.is_restricted(user_token["privileges"]):
        logger.warning(
            "User tried to send message but they are in restricted mode",
            extra={
                "token_id": token_id,
                "username": user_token["username"],
                "user_id": user_token["user_id"],
                "send_to": send_to,
            },
        )
        return ...

    if await osuToken.isSilenced(user_token["token_id"]):
        silence_time_left = await osuToken.getSilenceSecondsLeft(user_token["token_id"])
        await osuToken.enqueue(
            user_token["token_id"],
            serverPackets.silenceEndTime(silence_time_left),
        )

        logger.warning(
            "User tried to send message during silence",
            extra={
                "token_id": token_id,
                "username": user_token["username"],
                "user_id": user_token["user_id"],
                "send_to": send_to,
            },
        )
        return ...

    if not message.strip():
        logger.warning(
            "User tried to send an empty message",
            extra={
                "token_id": token_id,
                "username": user_token["username"],
                "user_id": user_token["user_id"],
                "send_to": send_to,
            },
        )
        return ...

    # optimise message
    if len(message) > 1024:
        message = f"{message[:1024]}... (truncated)"

    # We don't want people to do shit like ()[Aika].
    message = message.replace("()[", "[")

    # There are 3 types: bot interactions, public messages and private messages
    is_channel = send_to.startswith("#")
    if message.startswith("!") or message.startswith("\x01"):
        resp_code = await handle_interaction_with_bot(
            user_token=user_token,
            send_to=send_to,
            message=message,
        )
    elif is_channel:
        resp_code = await handle_public_message(
            user_token=user_token,
            send_to=send_to,
            message=message,
        )
    else:
        resp_code = await handle_private_message(
            user_token=user_token,
            send_to=send_to,
            message=message,
        )

    if not osuToken.is_staff(user_token["privileges"]):
        await osuToken.spamProtection(user_token["token_id"])

    if _check_for_gamer_ids(message):
        gamer_msg = f"{user_token['username']} @ {send_to}: {message}"
        if is_channel:
            gamer_msg = await osuToken.getMessagesBufferString(token_id)

        await audit_logs.send_log_as_discord_webhook(
            message=gamer_msg,
            discord_channel="ac_confidential",
        )
    else:
        logger.info(
            "User sent a chat message",
            extra={
                "token_id": token_id,
                "username": user_token["username"],
                "user_id": user_token["user_id"],
                "send_to": send_to,
            },
        )

    return resp_code
