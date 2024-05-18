from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

import settings
from common.constants import privileges
from common.log import audit_logs
from common.log import logger
from common.ripple import user_utils
from constants import CHATBOT_USER_ID
from constants import CHATBOT_USER_NAME
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


class ChatMessageError(str, Enum):
    UNKNOWN_CHANNEL = "UNKNOWN_CHANNEL"
    NO_CHANNEL_MEMBERSHIP = "NO_CHANNEL_MEMBERSHIP"
    USER_NOT_FOUND = "USER_NOT_FOUND"
    INSUFFICIENT_PRIVILEGES = "INSUFFICIENT_PRIVILEGES"
    SENDER_SILENCED = "SENDER_SILENCED"
    RECIPIENT_SILENCED = "RECIPIENT_SILENCED"
    SENDER_RESTRICTED = "SENDER_RESTRICTED"
    RECIPIENT_RESTRICTED = "RECIPIENT_RESTRICTED"
    BLOCKED_BY_RECIPIENT = "BLOCKED_BY_RECIPIENT"
    INVALID_MESSAGE_CONTENT = "INVALID_MESSAGE_CONTENT"


async def join_channel(
    channel_name: str,
    token_id: str,
    *,
    allow_instance_channels: bool = False,
) -> None:
    """
    Join a channel

    :param channel_name: channel name
    :param token: user token object of user that joins the channel.
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

    :param channel_name: channel name
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


def _should_audit_log_message(message: str) -> bool:
    return message in settings.AUDIT_LOG_MESSAGE_KEYWORDS


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


async def _unicast_private_message(
    *,
    sender_token: osuToken.Token,
    recipient_token: osuToken.Token,
    message: str,
) -> None:
    packet = serverPackets.sendMessage(
        fro=sender_token["username"],
        to=recipient_token["username"],
        message=message,
        fro_id=sender_token["user_id"],
    )
    await osuToken.enqueue(recipient_token["token_id"], packet)


async def _broadcast_public_message(
    *,
    sender_token: osuToken.Token,
    channel_name: str,
    client_channel_name: str,
    message: str,
) -> None:
    packet = serverPackets.sendMessage(
        fro=sender_token["username"],
        to=client_channel_name,
        message=message,
        fro_id=sender_token["user_id"],
    )

    await streamList.broadcast(
        f"chat/{channel_name}",
        packet,
        # We do not wish to send the packet to ourselves
        excluded_token_ids=[sender_token["token_id"]],
    )


async def _multicast_public_message(
    sender_token: osuToken.Token,
    channel_name: str,
    client_channel_name: str,
    message: str,
    *,
    recipient_token_ids: list[str] | None = None,
) -> None:
    if recipient_token_ids is None:
        recipient_token_ids = []

    packet = serverPackets.sendMessage(
        fro=sender_token["username"],
        to=client_channel_name,
        message=message,
        fro_id=sender_token["user_id"],
    )

    await streamList.multicast(
        stream_name=f"chat/{channel_name}",
        data=packet,
        recipient_token_ids=recipient_token_ids,
    )


async def _handle_private_bot_response(
    *,
    sender_token: osuToken.Token,
    response: Optional[chatbot.CommandResponse],
) -> None:
    if response is None:
        return

    aika_token = await tokenList.getTokenFromUserID(CHATBOT_USER_ID)
    assert aika_token is not None

    # chatbot's response
    await _unicast_private_message(
        sender_token=aika_token,
        recipient_token=sender_token,
        message=response["response"],
    )


async def _handle_public_bot_response(
    *,
    sender_token: osuToken.Token,
    recipient_name: str,
    message: str,
    chatbot_response: Optional[chatbot.CommandResponse],
) -> None:
    channel_name, client_channel_name = _get_client_channel_and_channel(
        user_token=sender_token,
        channel_name=recipient_name,
    )

    aika_token = await tokenList.getTokenFromUserID(CHATBOT_USER_ID)
    assert aika_token is not None

    # Response is only visible to user and some staff members
    if chatbot_response is not None and chatbot_response["hidden"]:
        enqueue_to = {  # I hate this part so much
            t["token_id"]
            for t in await osuToken.get_tokens()
            if (
                t["token_id"] != sender_token["token_id"]
                and osuToken.is_staff(t["privileges"])
                and t["user_id"] != CHATBOT_USER_ID
            )
        }

        # user's message
        await _multicast_public_message(
            sender_token=sender_token,
            channel_name=channel_name,
            client_channel_name=client_channel_name,
            message=message,
            recipient_token_ids=list(enqueue_to),
        )

        # chatbot's response
        enqueue_to.add(sender_token["token_id"])
        await _multicast_public_message(
            sender_token=aika_token,
            channel_name=channel_name,
            client_channel_name=client_channel_name,
            message=chatbot_response["response"],
            recipient_token_ids=list(enqueue_to),
        )
        return

    # There are 2 cases here: no response from chatbot
    # or response from chatbot visible to everyone eg. !roll
    await osuToken.addMessageInBuffer(sender_token["token_id"], channel_name, message)
    await _broadcast_public_message(  # user's message
        sender_token=sender_token,
        channel_name=channel_name,
        client_channel_name=client_channel_name,
        message=message,
    )

    if chatbot_response is not None:  # chatbot's response
        await _broadcast_public_message(
            sender_token=aika_token,
            channel_name=channel_name,
            client_channel_name=client_channel_name,
            message=chatbot_response["response"],
        )


async def _handle_interaction_with_bot(
    *,
    sender_token: osuToken.Token,
    recipient_name: str,
    message: str,
) -> Optional[ChatMessageError]:
    if message.startswith("!report"):
        recipient_name = CHATBOT_USER_NAME

    response = await chatbot.query(
        sender_token["username"],
        recipient_name,
        message,
    )

    logger.info(
        "User triggered chatbot interaction",
        extra={
            "sender_token_id": sender_token["token_id"],
            "sender_username": sender_token["username"],
            "sender_user_id": sender_token["user_id"],
            "recipient_name": recipient_name,
        },
    )

    is_channel = recipient_name.startswith("#")
    if is_channel:
        await _handle_public_bot_response(
            sender_token=sender_token,
            recipient_name=recipient_name,
            message=message,
            chatbot_response=response,
        )
    else:
        await _handle_private_bot_response(
            sender_token=sender_token,
            response=response,
        )

    return None


async def _handle_public_message(
    *,
    sender_token: osuToken.Token,
    recipient_name: str,
    message: str,
) -> Optional[ChatMessageError]:
    channel_name, client_channel_name = _get_client_channel_and_channel(
        user_token=sender_token,
        channel_name=recipient_name,
    )

    channel = await channelList.getChannel(channel_name)
    if channel is None:
        logger.warning(
            "User attempted to send a message to an unknown channel",
            extra={
                "sender_token_id": sender_token["token_id"],
                "sender_username": sender_token["username"],
                "sender_user_id": sender_token["user_id"],
                "channel_name": channel_name,
            },
        )
        return ChatMessageError.UNKNOWN_CHANNEL

    if channel["moderated"] and not osuToken.is_staff(sender_token["privileges"]):
        logger.warning(
            "User attempted to send a message to a moderated channel",
            extra={
                "sender_token_id": sender_token["token_id"],
                "sender_username": sender_token["username"],
                "sender_user_id": sender_token["user_id"],
                "channel_name": channel_name,
            },
        )
        return ChatMessageError.INSUFFICIENT_PRIVILEGES

    if channel_name not in await osuToken.get_joined_channels(sender_token["token_id"]):
        logger.warning(
            "User attempted to send a message to a channel they are not in",
            extra={
                "sender_token_id": sender_token["token_id"],
                "sender_username": sender_token["username"],
                "sender_user_id": sender_token["user_id"],
                "channel_name": channel_name,
            },
        )
        return ChatMessageError.NO_CHANNEL_MEMBERSHIP

    if (
        channel_name == "#premium"
        and sender_token["privileges"] & privileges.USER_PREMIUM == 0
    ):
        logger.warning(
            "User attempted to send a message to a premium channel without premium permissions",
            extra={
                "sender_token_id": sender_token["token_id"],
                "sender_username": sender_token["username"],
                "sender_user_id": sender_token["user_id"],
                "channel_name": channel_name,
            },
        )
        return ChatMessageError.INSUFFICIENT_PRIVILEGES

    if (
        channel_name == "#supporter"
        and sender_token["privileges"] & privileges.USER_DONOR == 0
    ):
        logger.warning(
            "User attempted to send a message to a supporter channel without supporter permissions",
            extra={
                "sender_token_id": sender_token["token_id"],
                "sender_username": sender_token["username"],
                "sender_user_id": sender_token["user_id"],
                "channel_name": channel_name,
            },
        )
        return ChatMessageError.INSUFFICIENT_PRIVILEGES

    if (
        not channel["public_write"]
        and not (
            channel_name.startswith("#multi_") or channel_name.startswith("#spect_")
        )
        and not osuToken.is_staff(sender_token["privileges"])
    ):
        logger.warning(
            "User attempted to send a message to a non-public channel without permissions",
            extra={
                "sender_token_id": sender_token["token_id"],
                "sender_username": sender_token["username"],
                "sender_user_id": sender_token["user_id"],
                "channel_name": channel_name,
            },
        )
        return ChatMessageError.INSUFFICIENT_PRIVILEGES

    await osuToken.addMessageInBuffer(sender_token["token_id"], channel_name, message)
    await _broadcast_public_message(
        sender_token=sender_token,
        channel_name=channel_name,
        client_channel_name=client_channel_name,
        message=message,
    )
    return None


async def _handle_private_message(
    *,
    sender_token: osuToken.Token,
    recipient_name: str,
    message: str,
) -> Optional[ChatMessageError]:
    recipient_token = await tokenList.getTokenFromUsername(recipient_name)
    if recipient_token is None:
        logger.warning(
            "User attempted to send a message to an unknown recipient",
            extra={
                "sender_token_id": sender_token["token_id"],
                "sender_username": sender_token["username"],
                "sender_user_id": sender_token["user_id"],
                "recipient_username": recipient_name,
            },
        )
        return ChatMessageError.USER_NOT_FOUND

    if recipient_token["tournament"]:
        logger.warning(
            "User attempted to send a message to a tournament client",
            extra={
                "sender_token_id": sender_token["token_id"],
                "sender_username": sender_token["username"],
                "sender_user_id": sender_token["user_id"],
                "recipient_username": recipient_token["username"],
                "recipient_user_id": recipient_token["user_id"],
            },
        )
        return ChatMessageError.USER_NOT_FOUND

    if await osuToken.isSilenced(recipient_token["token_id"]):
        await osuToken.enqueue(
            sender_token["token_id"],
            serverPackets.targetSilenced(recipient_token["username"]),
        )

        logger.warning(
            "User tried to send a message to a silenced user",
            extra={
                "sender_token_id": sender_token["token_id"],
                "sender_username": sender_token["username"],
                "sender_user_id": sender_token["user_id"],
                "recipient_name": recipient_token["username"],
                "recipient_user_id": recipient_token["user_id"],
            },
        )
        return ChatMessageError.RECIPIENT_SILENCED

    if osuToken.is_restricted(recipient_token["privileges"]):
        logger.warning(
            "User attempted to send a message to a restricted user",
            extra={
                "sender_token_id": sender_token["token_id"],
                "sender_username": sender_token["username"],
                "sender_user_id": sender_token["user_id"],
                "recipient_name": recipient_token["username"],
                "recipient_user_id": recipient_token["user_id"],
            },
        )
        return ChatMessageError.RECIPIENT_RESTRICTED

    if recipient_token["block_non_friends_dm"] and (
        sender_token["user_id"]
        not in await user_utils.get_friend_user_ids(recipient_token["user_id"])
    ):
        await osuToken.enqueue(
            sender_token["token_id"],
            serverPackets.targetBlockingDMs(recipient_token["username"]),
        )

        logger.warning(
            "User tried to send a message to a user that is blocking non-friends dms",
            extra={
                "sender_token_id": sender_token["token_id"],
                "sender_username": sender_token["username"],
                "sender_user_id": sender_token["user_id"],
                "recipient_username": recipient_token["username"],
                "recipient_user_id": recipient_token["user_id"],
            },
        )
        return ChatMessageError.BLOCKED_BY_RECIPIENT

    if await osuToken.awayCheck(
        recipient_token["token_id"],
        sender_token["user_id"],
    ):
        await _unicast_private_message(
            sender_token=recipient_token,
            recipient_token=sender_token,
            message=f"\x01ACTION is away: {recipient_token['away_message'] or ''}\x01",
        )

    await _unicast_private_message(
        sender_token=sender_token,
        recipient_token=recipient_token,
        message=message,
    )

    return None


async def _handle_message_from_chatbot(
    *,
    chatbot_token: osuToken.Token,
    recipient_name: str,
    message: str,
) -> Optional[ChatMessageError]:
    is_channel = recipient_name.startswith("#")

    if is_channel:
        channel_name, client_channel_name = _get_client_channel_and_channel(
            user_token=chatbot_token,
            channel_name=recipient_name,
        )

        channel = await channelList.getChannel(channel_name)
        if channel is None:
            logger.warning(
                "Chatbot attempted to send a message to an unknown channel",
                extra={
                    "chatbot_token_id": chatbot_token["token_id"],
                    "chatbot_username": chatbot_token["username"],
                    "chatbot_user_id": chatbot_token["user_id"],
                    "channel_name": channel_name,
                },
            )
            return ChatMessageError.UNKNOWN_CHANNEL

        await osuToken.addMessageInBuffer(
            chatbot_token["token_id"],
            channel_name,
            message,
        )
        await _broadcast_public_message(
            sender_token=chatbot_token,
            channel_name=channel_name,
            client_channel_name=client_channel_name,
            message=message,
        )

    else:
        recipient_token = await tokenList.getTokenFromUsername(recipient_name)
        if recipient_token is None:
            logger.warning(
                "Chatbot attempted to send a message to an unknown recipient",
                extra={
                    "chatbot_token_id": chatbot_token["token_id"],
                    "chatbot_username": chatbot_token["username"],
                    "chatbot_user_id": chatbot_token["user_id"],
                    "recipient_username": recipient_name,
                },
            )
            return ChatMessageError.USER_NOT_FOUND

        await _unicast_private_message(
            sender_token=chatbot_token,
            recipient_token=recipient_token,
            message=message,
        )

    logger.info(
        "Chatbot sent a message",
        extra={
            "chatbot_token_id": chatbot_token["token_id"],
            "chatbot_username": chatbot_token["username"],
            "chatbot_user_id": chatbot_token["user_id"],
            "recipient_name": recipient_name,
        },
    )
    return None


def _is_command_message(message: str) -> bool:
    return message.startswith("!") or message.startswith("\x01")


def _bot_can_observe_message(recipient_name: str) -> bool:
    is_channel = recipient_name.startswith("#")
    return is_channel or recipient_name == CHATBOT_USER_NAME


async def send_message(
    *,
    sender_token_id: str,
    recipient_name: str,
    message: str,
) -> Optional[ChatMessageError]:
    sender_token = await osuToken.get_token(sender_token_id)
    if sender_token is None:
        logger.warning(
            "User tried to send message but they are not connected to server",
            extra={"sender_token_id": sender_token_id},
        )
        return ChatMessageError.USER_NOT_FOUND

    if sender_token["user_id"] == CHATBOT_USER_ID:
        return await _handle_message_from_chatbot(
            chatbot_token=sender_token,
            recipient_name=recipient_name,
            message=message,
        )

    if sender_token["tournament"]:
        logger.warning(
            "User tried to send message but they are connected from tournament client",
            extra={
                "sender_token_id": sender_token_id,
                "sender_username": sender_token["username"],
                "sender_user_id": sender_token["user_id"],
                "recipient_name": recipient_name,
            },
        )
        return ChatMessageError.USER_NOT_FOUND

    if osuToken.is_restricted(sender_token["privileges"]):
        logger.warning(
            "User tried to send message but they are in restricted mode",
            extra={
                "sender_token_id": sender_token_id,
                "sender_username": sender_token["username"],
                "sender_user_id": sender_token["user_id"],
                "recipient_name": recipient_name,
            },
        )
        return ChatMessageError.SENDER_RESTRICTED

    if await osuToken.isSilenced(sender_token["token_id"]):
        silence_time_left = await osuToken.getSilenceSecondsLeft(
            sender_token["token_id"],
        )
        await osuToken.enqueue(
            sender_token["token_id"],
            serverPackets.silenceEndTime(silence_time_left),
        )

        logger.warning(
            "User tried to send message during silence",
            extra={
                "sender_token_id": sender_token_id,
                "sender_username": sender_token["username"],
                "sender_user_id": sender_token["user_id"],
                "recipient_name": recipient_name,
            },
        )
        return ChatMessageError.SENDER_SILENCED

    if not message.strip():
        logger.warning(
            "User tried to send an empty message",
            extra={
                "sender_token_id": sender_token_id,
                "sender_username": sender_token["username"],
                "sender_user_id": sender_token["user_id"],
                "recipient_name": recipient_name,
            },
        )
        return ChatMessageError.INVALID_MESSAGE_CONTENT

    # enforce a maximum message length
    if len(message) > 1024:
        message = f"{message[:1024]}... (truncated)"

    # We don't want people to do shit like ()[Aika].
    message = message.replace("()[", "[")

    # There are 3 types: bot interactions, public messages and private messages
    is_channel = recipient_name.startswith("#")
    if _bot_can_observe_message(recipient_name) and _is_command_message(message):
        response = await _handle_interaction_with_bot(
            sender_token=sender_token,
            recipient_name=recipient_name,
            message=message,
        )
    elif is_channel:
        response = await _handle_public_message(
            sender_token=sender_token,
            recipient_name=recipient_name,
            message=message,
        )
    else:
        response = await _handle_private_message(
            sender_token=sender_token,
            recipient_name=recipient_name,
            message=message,
        )

    if not osuToken.is_staff(sender_token["privileges"]):
        await osuToken.spamProtection(sender_token["token_id"])

    if _should_audit_log_message(message):
        audit_log_message = f"{sender_token['username']} @ {recipient_name}: {message}"
        if is_channel:
            audit_log_message = await osuToken.getMessagesBufferString(sender_token_id)

        await audit_logs.send_log_as_discord_webhook(
            message=audit_log_message,
            discord_channel="ac_confidential",
        )
    else:
        logger.info(
            "User sent a chat message",
            extra={
                "sender_token_id": sender_token_id,
                "sender_username": sender_token["username"],
                "sender_user_id": sender_token["user_id"],
                "recipient_name": recipient_name,
            },
        )

    return response
