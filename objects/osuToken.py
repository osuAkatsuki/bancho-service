from threading import Lock, RLock
from time import localtime, strftime, time
from typing import TYPE_CHECKING, Optional
from uuid import uuid4

from common.constants import actions, gameModes, privileges
from common.log import logUtils as log
from common.ripple import userUtils
from constants import exceptions, serverPackets
from events import logoutEvent
from helpers import chatHelper as chat
from objects import glob

if TYPE_CHECKING:
    from objects import channel
    from objects import osuToken


class token:
    __slots__ = (
        "userID",
        "username",
        "safeUsername",
        "privileges",
        "whitelist",
        "staff",
        "restricted",
        "irc",
        "kicked",
        "loginTime",
        "pingTime",
        "timeOffset",
        "streams",
        "tournament",
        "messagesBuffer",
        "blockNonFriendsDM",
        "spectators",
        "spectating",
        "spectatingUserID",
        "location",
        "joinedChannels",
        "ip",
        "country",
        "awayMessage",
        "sentAway",
        "matchID",
        "tillerino",
        "silenceEndTime",
        "queue",
        "spamRate",
        "actionID",
        "actionText",
        "actionMd5",
        "actionMods",
        "gameMode",
        "relax",
        "autopilot",
        "beatmapID",
        "rankedScore",
        "accuracy",
        "playcount",
        "totalScore",
        "gameRank",
        "pp",
        "token",
        "processingLock",
        "_bufferLock",
        "_spectLock",
    )

    def __init__(
        self,
        userID: int,
        token_: Optional[str] = None,
        ip: str = "",
        irc: bool = False,
        timeOffset: int = 0,
        tournament: bool = False,
    ) -> None:
        """
        Create a token object and set userID and token

        :param userID: user associated to this token
        :param token_: 	if passed, set token to that value
                        if not passed, token will be generated
        :param ip: client ip. optional.
        :param irc: if True, set this token as IRC client. Default: False.
        :param timeOffset: the time offset from UTC for this user. Default: 0.
        :param tournament: if True, flag this client as a tournement client. Default: True.
        """
        # Set stuff
        self.userID = userID

        res = glob.db.fetch(
            "SELECT username, username_safe, privileges, whitelist "
            "FROM users WHERE id = %s",
            [userID],
        )

        self.username = res["username"]
        self.safeUsername = res["username_safe"]
        self.privileges = res["privileges"]
        self.whitelist = res["whitelist"]  # zzz should be in privs

        # TODO: should be properties but code is shit
        self.staff = self.privileges & privileges.ADMIN_CHAT_MOD != 0
        self.restricted = (
            self.privileges & privileges.USER_PUBLIC == 0
            and self.privileges & privileges.USER_NORMAL != 0
        )
        # self.staff = self.privileges & privileges.ADMIN_CHAT_MOD > 0
        # self.whitelist = userUtils.getWhitelist(self.userID)
        # self.restricted = userUtils.isRestricted(self.userID)

        self.irc = irc
        self.kicked = False
        self.loginTime = int(time())
        self.pingTime = self.loginTime
        self.timeOffset = timeOffset
        self.streams = []
        self.tournament = tournament
        self.messagesBuffer = []
        self.blockNonFriendsDM = False

        # Default variables
        self.spectators = []

        # TODO: Move those two vars to a class
        self.spectating = None
        self.spectatingUserID = 0  # we need this in case we the host gets DCed

        self.location = [0.0, 0.0]
        self.joinedChannels = []
        self.ip = ip
        self.country = 0
        self.awayMessage = ""
        self.sentAway = []
        self.matchID = -1
        self.tillerino = [0, 0, -1.0]  # beatmap, mods, acc
        self.silenceEndTime = 0
        self.queue = bytearray()

        # Spam protection
        self.spamRate = 0

        # Stats cache
        self.actionID = actions.IDLE
        self.actionText = ""
        self.actionMd5 = ""
        self.actionMods = 0
        self.gameMode = gameModes.STD
        self.relax = 0
        self.autopilot = 0
        self.beatmapID = 0
        self.rankedScore = 0
        self.accuracy = 0.0
        self.playcount = 0
        self.totalScore = 0
        self.gameRank = 0
        self.pp = 0

        # Generate/set token
        self.token = token_ if token_ else str(uuid4())

        # Locks
        self.processingLock = (
            Lock()
        )  # Acquired while there's an incoming packet from this user
        self._bufferLock = Lock()  # Acquired while writing to packets buffer
        self._spectLock = RLock()

        # Set stats
        self.updateCachedStats()

        # If we have a valid ip, save bancho session in DB so we can cache LETS logins
        if ip != "":
            userUtils.saveBanchoSession(self.userID, self.ip)

        # Join main stream
        self.joinStream("main")

    # @property
    # def staff(self) -> bool:
    # 	return self.privileges & privileges.ADMIN_CHAT_MOD != 0

    # @property
    # def restricted(self) -> bool:
    # 	return self.privileges & privileges.USER_PUBLIC == 0

    def enqueue(self, data: bytes) -> None:
        """
        Add bytes (packets) to queue

        :param data: (packet) bytes to enqueue
        """
        with self._bufferLock:
            # Never enqueue for IRC clients or Aika
            if self.irc or self.userID < 999:
                return

            # Avoid memory leaks
            if len(data) < 10 * 10**6:
                self.queue += data
            else:
                log.warning(
                    f"{self.username}'s packets buffer is above 10M!! Lost some data!"
                )

    def resetQueue(self) -> None:
        """Resets the queue. Call when enqueued packets have been sent"""
        with self._bufferLock:
            self.queue.clear()

    def joinChannel(self, channelObject: "channel.channel") -> None:
        """
        Join a channel

        :param channelObject: channel object
        :raises: exceptions.userAlreadyInChannelException()
                 exceptions.channelNoPermissionsException()
        """
        if channelObject.name in self.joinedChannels:
            raise exceptions.userAlreadyInChannelException()

        # Make sure we have write permissions.
        if (
            ((
                channelObject.name == "#premium"
                and self.privileges & privileges.USER_PREMIUM == 0
            )
            or (
                channelObject.name == "#supporter"
                and self.privileges & privileges.USER_DONOR == 0
            )
            or (not channelObject.publicRead and not self.staff))
            and self.userID != 999
        ):
            raise exceptions.channelNoPermissionsException()

        self.joinedChannels.append(channelObject.name)
        self.joinStream(f"chat/{channelObject.name}")
        self.enqueue(serverPackets.channelJoinSuccess(channelObject.clientName))

    def partChannel(self, channelObject: "channel.channel") -> None:
        """
        Remove channel from joined channels list

        :param channelObject: channel object
        """
        self.joinedChannels.remove(channelObject.name)
        self.leaveStream(f"chat/{channelObject.name}")

    def setLocation(self, latitude: float, longitude: float) -> None:
        """
        Set client location

        :param latitude: latitude
        :param longitude: longitude
        """
        self.location = (latitude, longitude)

    def startSpectating(self, host: "osuToken.token") -> None:
        """
        Set the spectating user to userID, join spectator stream and chat channel
        and send required packets to host

        :param host: host osuToken object
        """
        with self._spectLock:
            # Stop spectating old client
            self.stopSpectating()

            # Set new spectator host
            self.spectating = host.token
            self.spectatingUserID = host.userID

            # Add us to host's spectator list
            host.spectators.append(self.token)

            # Create and join spectator stream
            streamName = f"spect/{host.userID}"
            glob.streams.add(streamName)
            self.joinStream(streamName)
            host.joinStream(streamName)

            # Send spectator join packet to host
            host.enqueue(serverPackets.addSpectator(self.userID))

            # Create and join #spectator (#spect_userid) channel
            glob.channels.addTempChannel(f"#spect_{host.userID}")
            chat.joinChannel(token=self, channel=f"#spect_{host.userID}", force=True)
            if len(host.spectators) == 1:
                # First spectator, send #spectator join to host too
                chat.joinChannel(
                    token=host, channel=f"#spect_{host.userID}", force=True
                )

            # Send fellow spectator join to all clients
            glob.streams.broadcast(
                streamName, serverPackets.fellowSpectatorJoined(self.userID)
            )

            # Get current spectators list
            for i in host.spectators:
                if i != self.token and i in glob.tokens.tokens:
                    self.enqueue(
                        serverPackets.fellowSpectatorJoined(
                            glob.tokens.tokens[i].userID
                        )
                    )

    def stopSpectating(self) -> None:
        """
        Stop spectating, leave spectator stream and channel
        and send required packets to host

        :return:
        """
        with self._spectLock:

            # Remove our userID from host's spectators
            if not self.spectating or self.spectatingUserID <= 0:
                return

            if self.spectating in glob.tokens.tokens:
                hostToken = glob.tokens.tokens[self.spectating]
            else:
                hostToken = None

            streamName = f"spect/{self.spectatingUserID}"

            # Remove us from host's spectators list,
            # leave spectator stream
            # and end the spectator left packet to host
            self.leaveStream(streamName)

            if hostToken:
                hostToken.spectators.remove(self.token)
                hostToken.enqueue(serverPackets.removeSpectator(self.userID))

                fellow_left_packet = serverPackets.fellowSpectatorLeft(self.userID)
                # and to all other spectators
                for i in hostToken.spectators:
                    if i in glob.tokens.tokens:
                        glob.tokens.tokens[i].enqueue(fellow_left_packet)

                # If nobody is spectating the host anymore, close #spectator channel
                # and remove host from spect stream too
                if not hostToken.spectators:
                    chat.partChannel(
                        token=hostToken,
                        channel=f"#spect_{hostToken.userID}",
                        kick=True,
                        force=True,
                    )
                    hostToken.leaveStream(streamName)

                # Console output
                # log.info("{} is no longer spectating {}. Current spectators: {}.".format(self.username, self.spectatingUserID, hostToken.spectators))

            # Part #spectator channel
            chat.partChannel(
                token=self,
                channel=f"#spect_{self.spectatingUserID}",
                kick=True,
                force=True,
            )

            # Set our spectating user to 0
            self.spectating = None
            self.spectatingUserID = 0

    def updatePingTime(self) -> None:
        """
        Update latest ping time to current time

        :return:
        """
        self.pingTime = int(time())

    def joinMatch(self, matchID: int) -> None:
        """
        Set match to matchID, join match stream and channel

        :param matchID: new match ID
        :return:
        """
        # Make sure the match exists
        if matchID not in glob.matches.matches:
            return

        # Match exists, get object
        match = glob.matches.matches[matchID]

        # Stop spectating
        self.stopSpectating()

        # Leave other matches
        if self.matchID > -1 and self.matchID != matchID:
            self.leaveMatch()

        # Try to join match
        if not match.userJoin(self):
            self.enqueue(serverPackets.matchJoinFail)
            return

        # Set matchID, join stream, channel and send packet
        self.matchID = matchID
        self.joinStream(match.streamName)
        chat.joinChannel(token=self, channel=f"#multi_{self.matchID}", force=True)
        self.enqueue(serverPackets.matchJoinSuccess(matchID))

        if match.isTourney:
            # Alert the user if we have just joined a tourney match
            self.enqueue(
                serverPackets.notification("You are now in a tournament match.")
            )
            # If an user joins, then the ready status of the match changes and
            # maybe not all users are ready.
            match.sendReadyStatus()

    def leaveMatch(self) -> None:
        """
        Leave joined match, match stream and match channel

        :return:
        """
        # Make sure we are in a match
        if self.matchID == -1:
            return

        # Part #multiplayer channel and streams (/ and /playing)
        chat.partChannel(
            token=self, channel=f"#multi_{self.matchID}", kick=True, force=True
        )
        self.leaveStream(f"multi/{self.matchID}")
        self.leaveStream(f"multi/{self.matchID}/playing")  # optional

        # Set usertoken match to -1
        leavingMatchID = self.matchID
        self.matchID = -1

        # Make sure the match exists
        if leavingMatchID not in glob.matches.matches:
            return

        # The match exists, get object
        match = glob.matches.matches[leavingMatchID]

        # Set slot to free
        match.userLeft(self)

        if match.isTourney:
            # If an user leaves, then the ready status of the match changes and
            # maybe all users are ready. Or maybe nobody is in the match anymore
            match.sendReadyStatus()

    def kick(
        self, message: str = "You we're kicked from the server.", reason: str = "kick"
    ) -> None:
        """
        Kick this user from the server

        :param message: Notification message to send to this user.
                        Default: "You we're kicked from the server."
        :param reason: Kick reason, used in logs. Default: "kick"
        :return:
        """
        # Send packet to target
        log.info(f"{self.username} has been disconnected. ({reason})")
        if message:
            self.enqueue(serverPackets.notification(message))

        self.enqueue(serverPackets.loginFailed)

        # Logout event
        logoutEvent.handle(self, deleteToken=self.irc)

    def silence(
        self, seconds: Optional[int] = None, reason: str = "", author: int = 999
    ) -> None:
        """
        Silences this user (db, packet and token)

        :param seconds: silence length in seconds. If None, get it from db. Default: None
        :param reason: silence reason. Default: empty string
        :param author: userID of who has silenced the user. Default: 999 (Aika)
        :return:
        """
        if seconds is None:
            # Get silence expire from db if needed
            seconds = max(0, userUtils.getSilenceEnd(self.userID) - int(time()))
        else:
            # Silence in db and token
            userUtils.silence(self.userID, seconds, reason, author)

        # Silence token
        self.silenceEndTime = int(time()) + seconds

        # Send silence packet to user
        self.enqueue(serverPackets.silenceEndTime(seconds))

        # Send silenced packet to everyone else
        glob.streams.broadcast("main", serverPackets.userSilenced(self.userID))

    def spamProtection(self, increaseSpamRate: bool = True) -> None:
        """
        Silences the user if is spamming.

        :param increaseSpamRate: set to True if the user has sent a new message. Default: True
        :return:
        """
        # Increase the spam rate if needed
        if increaseSpamRate:
            self.spamRate += 1

        # Silence the user if needed
        acceptable_rate = 10

        if self.spamRate > acceptable_rate:
            self.silence(600, "Spamming (auto spam protection)")

    def isSilenced(self) -> None:
        """
        Returns True if this user is silenced, otherwise False

        :return: True if this user is silenced, otherwise False
        """
        return self.silenceEndTime - int(time()) > 0

    def getSilenceSecondsLeft(self) -> int:
        """
        Returns the seconds left for this user's silence
        (0 if user is not silenced)

        :return: silence seconds left (or 0)
        """
        return max(0, self.silenceEndTime - int(time()))

    def updateCachedStats(self) -> None:
        """
        Update all cached stats for this token

        :return:
        """
        relax_int = 0
        if self.relax:
            relax_int = 1
        elif self.autopilot:
            relax_int = 2

        stats = userUtils.getUserStats(
            self.userID,
            self.gameMode,
            relax_int,
        )

        if not stats:
            log.warning("Stats query returned None")
            return

        self.rankedScore = stats["rankedScore"]
        self.accuracy = stats["accuracy"] / 100
        self.playcount = stats["playcount"]
        self.totalScore = stats["totalScore"]
        self.gameRank = stats["gameRank"]
        self.pp = stats["pp"]

    def checkRestricted(self) -> None:
        """
        Check if this token is restricted. If so, send Aika message

        :return:
        """
        oldRestricted = self.restricted
        self.restricted = userUtils.isRestricted(self.userID)
        if self.restricted:
            self.setRestricted()
        elif not self.restricted and oldRestricted != self.restricted:
            self.resetRestricted()

    def checkBanned(self) -> None:
        """
        Check if this user is banned. If so, disconnect it.

        :return:
        """
        if userUtils.isBanned(self.userID):
            self.enqueue(serverPackets.loginBanned)
            logoutEvent.handle(self, deleteToken=False)

    def setRestricted(self) -> None:
        """
        Set this token as restricted, send Aika message to user
        and send offline packet to everyone

        :return:
        """
        self.restricted = True
        chat.sendMessage(
            glob.BOT_NAME,
            self.username,
            "Your account is currently in restricted mode. Please visit Akatsuki's website for more information.",
        )

    def resetRestricted(self) -> None:
        """
        Send Aika message to alert the user that he has been unrestricted
        and he has to log in again.

        :return:
        """
        chat.sendMessage(
            glob.BOT_NAME,
            self.username,
            "Your account has been unrestricted! Please log in again.",
        )

    def joinStream(self, name) -> None:
        """
        Join a packet stream, or create it if the stream doesn't exist.

        :param name: stream name
        :return:
        """
        glob.streams.join(name, token=self.token)
        if name not in self.streams:
            self.streams.append(name)

    def leaveStream(self, name) -> None:
        """
        Leave a packets stream

        :param name: stream name
        :return:
        """
        glob.streams.leave(name, token=self.token)
        if name in self.streams:
            self.streams.remove(name)

    def leaveAllStreams(self) -> None:
        """
        Leave all joined packet streams

        :return:
        """
        for i in self.streams:
            self.leaveStream(i)

    def awayCheck(self, userID: int) -> bool:
        """
        Returns True if userID doesn't know that we are away
        Returns False if we are not away or if userID already knows we are away

        :param userID: original sender userID
        :return:
        """
        if not self.awayMessage or userID in self.sentAway:
            return False
        self.sentAway.append(userID)
        return True

    def addMessageInBuffer(self, chan: str, message: str) -> None:
        """
        Add a message in messages buffer (10 messages, truncated at 50 chars).
        Used as proof when the user gets reported.

        :param chan: channel
        :param message: message content
        :return:
        """
        if len(self.messagesBuffer) > 15:
            self.messagesBuffer = self.messagesBuffer[1:]
        self.messagesBuffer.append(
            f"{strftime('%H:%M', localtime())} - {self.username}@{chan}: {message[:50]}"
        )

    def getMessagesBufferString(self) -> str:
        """
        Get the content of the messages buffer as a string

        :return: messages buffer content as a string
        """
        return "\n".join(x for x in self.messagesBuffer)
