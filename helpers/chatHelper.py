from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING
from typing import TypedDict

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
from objects.chatbot import ChatbotResponse

if TYPE_CHECKING:
    from typing import Optional


MAXIMUM_MESSAGE_LENGTH = 1000


class SendMessageError(str, Enum):
    UNKNOWN_CHANNEL = "UNKNOWN_CHANNEL"
    NO_CHANNEL_MEMBERSHIP = "NO_CHANNEL_MEMBERSHIP"
    USER_NOT_FOUND = "USER_NOT_FOUND"
    SENDER_CLIENT_STREAM_UNSUPPORTED = "SENDER_CLIENT_STREAM_UNSUPPORTED"
    RECIPIENT_CLIENT_STREAM_UNSUPPORTED = "RECIPIENT_CLIENT_STREAM_UNSUPPORTED"
    INSUFFICIENT_PRIVILEGES = "INSUFFICIENT_PRIVILEGES"
    SENDER_SILENCED = "SENDER_SILENCED"
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
    token: osuToken.Token | None = None

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
    token: osuToken.Token | None = None

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


class ContextualChannelNames(TypedDict):
    server_name: str  # e.g. #mp_123
    client_name: str  # e.g. #multiplayer


def _get_contextual_channel_names(
    channel_name: str,
    *,
    user_token: osuToken.Token,
) -> ContextualChannelNames:
    """\
    Find the channel names from the perspective
    of both the client and the server.
    """
    if channel_name == "#spectator":
        if user_token["spectating_user_id"] is None:
            spectating_user_id = user_token["user_id"]
        else:
            spectating_user_id = user_token["spectating_user_id"]

        server_channel_name = f"#spect_{spectating_user_id}"
        client_channel_name = "#spectator"

    elif channel_name == "#multiplayer":
        server_channel_name = f"#mp_{user_token['match_id']}"
        client_channel_name = "#multiplayer"

    elif channel_name.startswith("#spect_"):
        server_channel_name = channel_name
        client_channel_name = "#spectator"

    elif channel_name.startswith("#mp_"):
        server_channel_name = channel_name
        client_channel_name = "#multiplayer"
    else:
        server_channel_name = channel_name
        client_channel_name = channel_name

    return {
        "server_name": server_channel_name,
        "client_name": client_channel_name,
    }


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
    channel_names: ContextualChannelNames,
    message: str,
) -> None:
    packet = serverPackets.sendMessage(
        fro=sender_token["username"],
        to=channel_names["client_name"],
        message=message,
        fro_id=sender_token["user_id"],
    )

    await streamList.broadcast(
        f"chat/{channel_names['server_name']}",
        packet,
        # We don't send the packet to the sender because
        # their game already displays what they sent
        excluded_token_ids=[sender_token["token_id"]],
    )


async def _multicast_public_message(
    *,
    sender_token: osuToken.Token,
    channel_names: ContextualChannelNames,
    message: str,
    recipient_token_ids: list[str],
) -> None:
    packet = serverPackets.sendMessage(
        fro=sender_token["username"],
        to=channel_names["client_name"],
        message=message,
        fro_id=sender_token["user_id"],
    )

    await streamList.multicast(
        stream_name=f"chat/{channel_names['server_name']}",
        data=packet,
        recipient_token_ids=recipient_token_ids,
    )


def _is_chatbot_interaction_message(message: str) -> bool:
    return message.startswith("!") or message.startswith("\x01")


def _chatbot_can_observe_message(recipient_name: str) -> bool:
    is_channel = recipient_name.startswith("#")
    return is_channel or recipient_name == CHATBOT_USER_NAME


def _is_chatbot_interaction(message: str, recipient_name: str) -> bool:
    return _is_chatbot_interaction_message(message) and _chatbot_can_observe_message(
        recipient_name,
    )


async def _handle_public_message(
    *,
    sender_token: osuToken.Token,
    recipient_name: str,
    message: str,
) -> SendMessageError | None:
    channel_names = _get_contextual_channel_names(
        channel_name=recipient_name,
        user_token=sender_token,
    )

    channel = await channelList.getChannel(channel_names["server_name"])
    if channel is None:
        logger.warning(
            "User attempted to send a message to an unknown channel",
            extra={
                "sender_token_id": sender_token["token_id"],
                "sender_username": sender_token["username"],
                "sender_user_id": sender_token["user_id"],
                "channel_names": channel_names,
            },
        )
        return SendMessageError.UNKNOWN_CHANNEL

    if channel["moderated"] and not osuToken.is_staff(sender_token["privileges"]):
        logger.warning(
            "User attempted to send a message to a moderated channel",
            extra={
                "sender_token_id": sender_token["token_id"],
                "sender_username": sender_token["username"],
                "sender_user_id": sender_token["user_id"],
                "channel_names": channel_names,
            },
        )
        return SendMessageError.INSUFFICIENT_PRIVILEGES

    if channel_names["server_name"] not in await osuToken.get_joined_channels(
        sender_token["token_id"],
    ):
        logger.warning(
            "User attempted to send a message to a channel they are not in",
            extra={
                "sender_token_id": sender_token["token_id"],
                "sender_username": sender_token["username"],
                "sender_user_id": sender_token["user_id"],
                "channel_names": channel_names,
            },
        )
        return SendMessageError.NO_CHANNEL_MEMBERSHIP

    if (
        channel_names["client_name"] == "#premium"
        and sender_token["privileges"] & privileges.USER_PREMIUM == 0
    ):
        logger.warning(
            "User attempted to send a message to a premium channel without premium permissions",
            extra={
                "sender_token_id": sender_token["token_id"],
                "sender_username": sender_token["username"],
                "sender_user_id": sender_token["user_id"],
                "channel_names": channel_names,
            },
        )
        return SendMessageError.INSUFFICIENT_PRIVILEGES

    if (
        channel_names["client_name"] == "#supporter"
        and sender_token["privileges"] & privileges.USER_DONOR == 0
    ):
        logger.warning(
            "User attempted to send a message to a supporter channel without supporter permissions",
            extra={
                "sender_token_id": sender_token["token_id"],
                "sender_username": sender_token["username"],
                "sender_user_id": sender_token["user_id"],
                "channel_names": channel_names,
            },
        )
        return SendMessageError.INSUFFICIENT_PRIVILEGES

    if (
        not channel["public_write"]
        and channel_names["client_name"] not in {"#multiplayer", "#spectator"}
        and not osuToken.is_staff(sender_token["privileges"])
    ):
        logger.warning(
            "User attempted to send a message to a non-public channel without permissions",
            extra={
                "sender_token_id": sender_token["token_id"],
                "sender_username": sender_token["username"],
                "sender_user_id": sender_token["user_id"],
                "channel_names": channel_names,
            },
        )
        return SendMessageError.INSUFFICIENT_PRIVILEGES

    await osuToken.addMessageInBuffer(
        sender_token["token_id"],
        channel_names["server_name"],
        message,
    )

    recipient_tokens = [
        token
        for token in await osuToken.get_tokens()
        if (
            # Never send messages to any chatbot sessions
            token["user_id"] != CHATBOT_USER_ID
            # Never send our messages to our own session
            and token["token_id"] != sender_token["token_id"]
        )
    ]

    chatbot_response: ChatbotResponse | None = None
    if _is_chatbot_interaction(message, recipient_name):
        if message.startswith("!report"):
            recipient_name = CHATBOT_USER_NAME

        chatbot_response = await chatbot.query(
            sender_token["username"],
            channel_names["server_name"],
            message,
        )

        logger.info(
            "User triggered chatbot interaction",
            extra={
                "sender_token_id": sender_token["token_id"],
                "sender_username": sender_token["username"],
                "sender_user_id": sender_token["user_id"],
                "channel_names": channel_names,
                "bot_responded": chatbot_response is not None,
            },
        )

        if chatbot_response is not None and chatbot_response["hidden"]:
            # This is a "hidden" response from a chatbot interaction.
            # This means that only the sender and staff members are
            # able to see the command invocation and chatbot response.
            # TODO: "hidden" is more like e.g. "private_interaction".
            recipient_tokens = [
                token
                for token in recipient_tokens
                if osuToken.is_staff(token["privileges"])
            ]

    recipient_token_ids = [t["token_id"] for t in recipient_tokens]

    # Send the user's message
    await _multicast_public_message(
        sender_token=sender_token,
        channel_names=channel_names,
        message=message,
        recipient_token_ids=recipient_token_ids,
    )

    if chatbot_response is not None:
        chatbot_token = await osuToken.get_token_by_user_id(CHATBOT_USER_ID)
        assert chatbot_token is not None

        # We want to send the chatbot's response to the initial sender
        recipient_token_ids.append(sender_token["token_id"])

        # Send the chatbot's response
        await _multicast_public_message(
            sender_token=chatbot_token,
            channel_names=channel_names,
            message=chatbot_response["response"],
            recipient_token_ids=recipient_token_ids,
        )

    return None


async def _handle_private_message(
    *,
    sender_token: osuToken.Token,
    recipient_name: str,
    message: str,
) -> SendMessageError | None:
    recipient_token = await osuToken.get_token_by_username(recipient_name)
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
        return SendMessageError.USER_NOT_FOUND

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
        return SendMessageError.RECIPIENT_CLIENT_STREAM_UNSUPPORTED

    if await osuToken.isSilenced(recipient_token["token_id"]):
        await osuToken.enqueue(
            sender_token["token_id"],
            serverPackets.targetSilenced(recipient_token["username"]),
        )

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
        return SendMessageError.RECIPIENT_RESTRICTED

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
        return SendMessageError.BLOCKED_BY_RECIPIENT

    if await osuToken.awayCheck(
        recipient_token["token_id"],
        sender_token["user_id"],
    ):
        assert recipient_token["away_message"] is not None  # checked by awayCheck()
        await _unicast_private_message(
            sender_token=recipient_token,
            recipient_token=sender_token,
            message=f"\x01ACTION is away: {recipient_token['away_message']}\x01",
        )

    if _is_chatbot_interaction(message, recipient_name):
        chatbot_response = await chatbot.query(
            sender_token["username"],
            recipient_name,
            message,
        )
        if chatbot_response is not None:
            chatbot_token = await osuToken.get_token_by_user_id(CHATBOT_USER_ID)
            assert chatbot_token is not None

            # chatbot's response
            await _unicast_private_message(
                sender_token=chatbot_token,
                recipient_token=sender_token,
                message=chatbot_response["response"],
            )

        logger.info(
            "User triggered chatbot interaction",
            extra={
                "sender_token_id": sender_token["token_id"],
                "sender_username": sender_token["username"],
                "sender_user_id": sender_token["user_id"],
                "recipient_name": recipient_name,
                "bot_responded": chatbot_response is not None,
            },
        )

    else:  # Non-chatbot interaction
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
) -> SendMessageError | None:
    is_channel = recipient_name.startswith("#")

    if is_channel:
        channel_names = _get_contextual_channel_names(
            channel_name=recipient_name,
            user_token=chatbot_token,
        )

        channel = await channelList.getChannel(channel_names["server_name"])
        if channel is None:
            logger.warning(
                "Chatbot attempted to send a message to an unknown channel",
                extra={
                    "chatbot_token_id": chatbot_token["token_id"],
                    "chatbot_username": chatbot_token["username"],
                    "chatbot_user_id": chatbot_token["user_id"],
                    "channel_names": channel_names,
                },
            )
            return SendMessageError.UNKNOWN_CHANNEL

        await _broadcast_public_message(
            sender_token=chatbot_token,
            channel_names=channel_names,
            message=message,
        )

    else:
        recipient_token = await osuToken.get_token_by_username(recipient_name)
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
            return SendMessageError.USER_NOT_FOUND

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


async def send_message(
    *,
    sender_token_id: str,
    recipient_name: str,
    message: str,
) -> SendMessageError | None:
    sender_token = await osuToken.get_token(sender_token_id)
    if sender_token is None:
        logger.warning(
            "User tried to send message but they are not connected to server",
            extra={"sender_token_id": sender_token_id},
        )
        return SendMessageError.USER_NOT_FOUND

    # Fast-track for when the chatbot is sending a message.
    # In this case, we can assume a higher degree of trust.
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
        return SendMessageError.SENDER_CLIENT_STREAM_UNSUPPORTED

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
        return SendMessageError.SENDER_RESTRICTED

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
        return SendMessageError.SENDER_SILENCED

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
        return SendMessageError.INVALID_MESSAGE_CONTENT

    # Enforce a maximum message length
    if len(message) > MAXIMUM_MESSAGE_LENGTH:
        message = f"{message[:MAXIMUM_MESSAGE_LENGTH]}... (truncated)"

    # There are 2 types of message: public (channel) and private (DM)
    is_channel = recipient_name.startswith("#")
    if is_channel:
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

    if isinstance(response, SendMessageError):
        return response

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
