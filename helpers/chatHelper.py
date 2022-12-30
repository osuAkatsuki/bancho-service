from __future__ import annotations

from typing import TYPE_CHECKING
from common import channel_utils

import settings
from common.constants import mods
from common.constants import privileges
from common.log import logUtils as log
from common.ripple import userUtils
from constants import exceptions
from constants import serverPackets
from events import logoutEvent
from objects import fokabot, stream
from objects import glob, streamList,channelList

if TYPE_CHECKING:
    from typing import Optional

    from objects.osuToken import token


def joinChannel(
    userID: int = 0,
    channel_name: str = "",
    token: Optional[token] = None,
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
    try:
        # Get token if not defined
        if token is None:
            token = glob.tokens.getTokenFromUserID(userID)
            # Make sure the token exists
            if token is None:
                raise exceptions.userNotFoundException
        else:
            token = token

        # Normal channel, do check stuff
        # Make sure the channel exists
        if channel_name not in channelList.getChannelNames():
            raise exceptions.channelUnknownException()

        # Make sure a game client is not trying to join a #multi_ or #spect_ channel manually
        channel = channelList.getChannel(channel_name)
        if channel is None:
            raise exceptions.channelUnknownException()

        if channel["instance"] and not token.irc and not force:
            raise exceptions.channelUnknownException()

        # Add the channel to our joined channel
        token.joinChannel(channel_name)

        # Send channel joined (IRC)
        if settings.IRC_ENABLE and not toIRC:
            glob.ircServer.banchoJoinChannel(token.username, channel_name)

        # Console output
        # log.info(f"{token.username} joined channel {channel}")

        # IRC code return
        return 0
    except exceptions.channelNoPermissionsException:
        log.warning(
            f"{token.username} attempted to join channel {channel_name}, but they have no read permissions.",
        )
        return 403
    except exceptions.channelUnknownException:
        log.warning(
            f"{token.username} attempted to join an unknown channel ({channel_name}).",
        )
        return 403
    except exceptions.userAlreadyInChannelException:
        log.warning(f"User {token.username} already in channel {channel_name}.")
        return 403
    except exceptions.userNotFoundException:
        log.warning("User not connected to IRC/Bancho.")
        return 403  # idk


def partChannel(
    userID: int = 0,
    channel_name: str = "",
    token: Optional[token] = None,
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
    try:
        # Make sure the client is not drunk and sends partChannel when closing a PM tab
        if not channel_name.startswith("#"):
            return 0

        # Get token if not defined
        if token is None:
            token = glob.tokens.getTokenFromUserID(userID)
            # Make sure the token exists
            if token is None:
                raise exceptions.userNotFoundException()
        else:
            token = token

        # Determine internal/client name if needed
        # (toclient is used clientwise for #multiplayer and #spectator channels)
        channelClient = channel_name
        if channel_name == "#spectator":
            if token.spectating is None:
                s = userID
            else:
                s = token.spectatingUserID
            channel_name = f"#spect_{s}"
        elif channel_name == "#multiplayer":
            channel_name = f"#multi_{token.matchID}"
        elif channel_name.startswith("#spect_"):
            channelClient = "#spectator"
        elif channel_name.startswith("#multi_"):
            channelClient = "#multiplayer"

        # Make sure the channel exists
        if channel_name not in channelList.getChannelNames():
            raise exceptions.channelUnknownException()

        # Make sure a game client is not trying to join a #multi_ or #spect_ channel manually
        channel = channelList.getChannel(channel_name)
        if channel is None:
            raise exceptions.channelUnknownException()

        if channel['instance'] and not token.irc and not force:
            raise exceptions.channelUnknownException()

        # Make sure the user is in the channel
        if channel_name not in token.joinedChannels:
            raise exceptions.userNotInChannelException()

        # Part channel (token-side and channel-side)
        token.partChannel(channel_name)

        # Delete temporary channel if everyone left
        key = f"chat/{channel_name}"
        if key in streamList.getStreams():
            if (
                channel["instance"]
                and stream.getClientCount(key) - 1
                == 0
            ):
                channelList.removeChannel(channel_name)

        # Force close tab if needed
        # NOTE: Maybe always needed, will check later
        if kick:
            token.enqueue(serverPackets.channelKicked(channelClient))

        # IRC part
        if settings.IRC_ENABLE and toIRC:
            glob.ircServer.banchoPartChannel(token.username, channel_name)

        # Console output
        # log.info(f"{token.username} parted channel {channel_name} ({channelClient}).")

        # Return IRC code
        return 0
    except exceptions.channelUnknownException:
        log.warning(
            f"{token.username} attempted to part an unknown channel ({channel_name}).",
        )
        return 403
    except exceptions.userNotInChannelException:
        log.warning(
            f"{token.username} attempted to part {channel_name}, but he's not in that channel.",
        )
        return 442
    except exceptions.userNotFoundException:
        log.warning("User not connected to IRC/Bancho.")
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
]


def sendMessage(
    fro: Optional[str] = "",
    to: str = "",
    message: str = "",
    token: Optional[token] = None,
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
    try:
        # tokenString = ""
        # Get token object if not passed
        if token is None:
            token = glob.tokens.getTokenFromUsername(fro)
            if token is None:
                raise exceptions.userNotFoundException()
        else:
            # token object alredy passed, get its string and its username (fro)
            fro = token.username
            # tokenString = token.token

        # Make sure this is not a tournament client
        if token.tournament:
            raise exceptions.userTournamentException()

        # Make sure the user is not in restricted mode
        if token.restricted:
            raise exceptions.userRestrictedException()

        # Make sure the user is not silenced
        if token.isSilenced():
            raise exceptions.userSilencedException()

        # Redirect !report to FokaBot
        if message.startswith("!report"):
            to = glob.BOT_NAME

        # Determine internal name if needed
        # (toclient is used clientwise for #multiplayer and #spectator channels)
        toClient = to
        if to == "#spectator":
            if token.spectating is None:
                s = token.userID
            else:
                s = token.spectatingUserID
            to = f"#spect_{s}"
        elif to == "#multiplayer":
            to = f"#multi_{token.matchID}"
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
            channel = channelList.getChannel(to)
            if channel is None:
                raise exceptions.channelUnknownException()

            # Make sure the channel is not in moderated mode
            if channel["moderated"] and not token.staff:
                raise exceptions.channelModeratedException()

            # Make sure we are in the channel
            if to not in token.joinedChannels:
                # I'm too lazy to put and test the correct IRC error code here...
                # but IRC is not strict at all so who cares
                raise exceptions.channelNoPermissionsException()

            # Make sure we have write permissions.
            if (
                # you need premium for #premium
                (to == "#premium" and token.privileges & privileges.USER_PREMIUM == 0) and
                # you need supporter for #supporter
                (to == "#supporter" and token.privileges & privileges.USER_DONOR == 0)
                and not (channel["publicWrite"] or token.staff)
            ):
                raise exceptions.channelNoPermissionsException()

            # Check message for commands
            if not action_msg:
                fokaMessage = fokabot.fokabotResponse(token.username, to, message)
            else:
                fokaMessage = None

                # check for /np (rly bad lol)
                npmsg = message.split(" ")[1:]
                if npmsg[1] in ("playing", "watching", "editing"):
                    has_mods = True
                    index = 2
                elif npmsg[1] == "listening":
                    has_mods = False
                    index = 3
                else:
                    index = None

                if index is not None:
                    if not (beatmap_url := npmsg[index][1:]).startswith("https://"):
                        return

                    _mods = 0

                    if has_mods:
                        mapping = {
                            "-Easy": mods.EASY,
                            "-NoFail": mods.NOFAIL,
                            "+Hidden": mods.HIDDEN,
                            "+HardRock": mods.HARDROCK,
                            "+Nightcore": mods.NIGHTCORE,
                            "+DoubleTime": mods.DOUBLETIME,
                            "-HalfTime": mods.HALFTIME,
                            "+Flashlight": mods.FLASHLIGHT,
                            "-SpunOut": mods.SPUNOUT,
                            "~Relax~": mods.RELAX,
                        }

                        npmsg[-1] = npmsg[-1].replace("\x01", "")

                        for i in npmsg[index + 1 :]:
                            if i in mapping.keys():
                                _mods |= mapping[i]

                    match = fokabot.npRegex.match(beatmap_url)

                    if match:  # should always match?
                        # Get beatmap id from URL
                        beatmap_id = int(match["id"])

                        # Return tillerino message
                        token.tillerino = [beatmap_id, _mods, -1.0]
                    else:
                        log.error("failed to parse beatmap url? (chatHelper)")

            msg_packet = serverPackets.sendMessage(
                fro=token.username,
                to=toClient,
                message=message,
                fro_id=token.userID,
            )

            if fokaMessage:
                if fokaMessage["hidden"]:  # Send to user & gmt+
                    with glob.tokens:  # Generate admin token list
                        send_to = {
                            i.token
                            for i in glob.tokens.tokens.values()
                            if i != token and i.staff and i.userID != 999
                        }

                    # Send their command
                    streamList.broadcast_limited(f"chat/{to}", msg_packet, send_to)

                    # Send Aika's response
                    send_to.add(token.token)
                    response_packet = serverPackets.sendMessage(
                        fro=glob.BOT_NAME,
                        to=toClient,
                        message=fokaMessage["response"],
                        fro_id=999,
                    )
                    streamList.broadcast_limited(
                        f"chat/{to}",
                        response_packet,
                        send_to,
                    )
                else:  # Send to all streams
                    token.addMessageInBuffer(to, message)
                    streamList.broadcast(f"chat/{to}", msg_packet, but=[token.token])
                    sendMessage(glob.BOT_NAME, to, fokaMessage["response"])
            else:
                token.addMessageInBuffer(to, message)
                streamList.broadcast(f"chat/{to}", msg_packet, but=[token.token])
        else:
            # USER
            # Make sure recipient user is connected
            recipientToken = glob.tokens.getTokenFromUsername(to)
            if recipientToken is None:
                raise exceptions.userNotFoundException()

            # Make sure the recipient is not a tournament client
            if recipientToken.tournament:
                raise exceptions.userTournamentException()

            # Notify the sender that the recipient is silenced.
            if recipientToken.isSilenced():
                token.enqueue(
                    serverPackets.targetSilenced(
                        to=to,
                        fro=token.username,
                        fro_id=token.userID,
                    ),
                )

            if token.username != glob.BOT_NAME:
                # Make sure the recipient is not restricted or we are bot
                if recipientToken.restricted:
                    raise exceptions.userRestrictedException()

                # TODO: Make sure the recipient has not disabled PMs for non-friends or he's our friend
                if (
                    recipientToken.blockNonFriendsDM
                    and token.userID
                    not in userUtils.getFriendList(recipientToken.userID)
                ):
                    token.enqueue(
                        serverPackets.targetBlockingDMs(
                            to=to,
                            fro=token.username,
                            fro_id=token.userID,
                        ),
                    )
                    raise exceptions.userBlockingDMsException

            # Away check
            if recipientToken.awayCheck(token.userID):
                sendMessage(
                    to,
                    fro,
                    f"\x01ACTION is away: {recipientToken.awayMessage}\x01",
                )

            if to == glob.BOT_NAME:
                # Check message for commands
                fokaMessage = fokabot.fokabotResponse(token.username, to, message)

                if fokaMessage:
                    sendMessage(glob.BOT_NAME, fro, fokaMessage["response"])
            else:
                packet = serverPackets.sendMessage(
                    fro=token.username,
                    to=toClient,
                    message=message,
                    fro_id=token.userID,
                )
                recipientToken.enqueue(packet)

        # Spam protection (ignore staff)
        if not token.staff:
            token.spamProtection()

        if (
            any([bytes(gid).decode() in message for gid in gamer_ids])
            and not action_msg
            and not token.staff
        ):
            webhook = "ac_confidential"
        else:
            webhook = None

        if isChannel:
            if webhook:
                log.chat(f"{token.getMessagesBufferString()}", webhook)
            else:
                log.chat(f"{token.username} @ {to}: {message}")
        else:
            log.pm(f"{fro} @ {to}: {message}", webhook)

        return 0
    except exceptions.userSilencedException:
        token.enqueue(serverPackets.silenceEndTime(token.getSilenceSecondsLeft()))
        log.warning(f"{token.username} tried to send a message during silence.")
        return 404
    except exceptions.channelModeratedException:
        log.warning(
            f"{token.username} tried to send a message to a channel that is in moderated mode ({to}).",
        )
        return 404
    except exceptions.channelUnknownException:
        log.warning(
            f"{token.username} tried to send a message to an unknown channel ({to}).",
        )
        return 403
    except exceptions.channelNoPermissionsException:
        log.warning(
            f"{token.username} tried to send a message to channel {to}, but they have no write permissions.",
        )
        return 404
    except exceptions.userRestrictedException:
        log.warning(
            f"{token.username} tried to send a message {to}, but the recipient is in restricted mode.",
        )
        return 404
    except exceptions.userTournamentException:
        log.warning(
            f"{token.username} tried to send a message {to}, but the recipient is a tournament client.",
        )
        return 404
    except exceptions.userNotFoundException:
        log.warning("User not connected to IRC/Bancho.")
        return 401
    except exceptions.userBlockingDMsException:
        log.warning(
            f"{token.username} tried to send a message to {to}, but the recipient is blocking non-friends dms.",
        )
        return 404
    except exceptions.invalidArgumentsException:
        log.warning(f"{token.username} tried to send an invalid message to {to}.")
        return 404
    except Exception as e:  # unhandled
        log.warning(f"chatHelper {e}")


""" IRC-Bancho Connect/Disconnect/Join/Part interfaces"""


def fixUsernameForBancho(username: str) -> str:
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
    result = glob.db.fetch(
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


def IRCConnect(username: str) -> None:
    """
    Handle IRC login bancho-side.
    Add token and broadcast login packet.

    :param username: username
    :return:
    """
    userID = userUtils.getID(username)
    if not userID:
        log.warning(f"{username} doesn't exist.")
        return

    with glob.tokens:
        glob.tokens.deleteOldTokens(userID)
        glob.tokens.addToken(userID, irc=True)

    streamList.broadcast("main", serverPackets.userPanel(userID))
    log.info(f"{username} logged in from IRC.")


def IRCDisconnect(username: str) -> None:
    """
    Handle IRC logout bancho-side.
    Remove token and broadcast logout packet.

    :param username: username
    :return:
    """
    token = glob.tokens.getTokenFromUsername(username)
    if token is None:
        log.warning(f"{username} doesn't exist.")
        return

    logoutEvent.handle(token)
    log.info(f"{username} disconnected from IRC.")


def IRCJoinChannel(username: str, channel: str) -> Optional[int]:
    """
    Handle IRC channel join bancho-side.

    :param username: username
    :param channel: channel name
    :return: IRC return code
    """
    userID = userUtils.getID(username)
    if not userID:
        log.warning(f"{username} doesn't exist.")
        return

    # NOTE: This should have also `toIRC` = False` tho,
    # since we send JOIN message later on ircserver.py.
    # Will test this later
    return joinChannel(userID, channel)


def IRCPartChannel(username: str, channel: str) -> Optional[int]:
    """
    Handle IRC channel part bancho-side.

    :param username: username
    :param channel: channel name
    :return: IRC return code
    """
    userID = userUtils.getID(username)
    if not userID:
        log.warning(f"{username} doesn't exist.")
        return

    return partChannel(userID, channel)


def IRCAway(username: str, message: str) -> Optional[int]:
    """
    Handle IRC away command bancho-side.

    :param username:
    :param message: away message
    :return: IRC return code
    """
    userID = userUtils.getID(username)
    if not userID:
        log.warning(f"{username} doesn't exist.")
        return # TODO: should this be returning a code?

    glob.tokens.getTokenFromUserID(userID).awayMessage = message
    return 306 if message else 305
