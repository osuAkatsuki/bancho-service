"""
This file has been _rewritten_ taking by reference code from
miniircd (https://github.com/jrosdahl/miniircd)
by Joel Rosdahl, licensed under the GNU GPL 2 License.

Most of the reference code from miniircd was used for the low-level logic.
The high-level code has been rewritten to make it compatible with bancho-service.
"""
# NOTE(2023-08-10): this is currently deprecated within akatsuki and is not functional
# here because we may use it in the future - perhaps for deletion eventually.
from __future__ import annotations

import hashlib
import re
import select
import socket
import sys
import time

import settings
from common.log import logger
from common.ripple import userUtils
from helpers import chatHelper as chat
from objects import channelList
from objects import glob
from objects import osuToken
from objects import stream
from objects import streamList
from objects import tokenList


class Client:
    __linesep_regexp = re.compile(r"\r?\n")

    def __init__(self, server, sock):
        """
        Initialize a Client object

        :param server: server object
        :param sock: socket connection object
        :return:
        """
        self.__timestamp = time.time()
        self.__readbuffer = ""
        self.__writebuffer = ""
        self.__sentPing = False
        self.__handleCommand = self.passHandler

        self.server = server
        self.socket = sock
        (self.ip, self.port) = sock.getpeername()
        self.IRCUsername = ""
        self.banchoUsername = ""
        self.supposedUsername = ""
        self.supposedUserID = 0
        self.joinedChannels = []

    def messageChannel(self, channel, command, message, includeSelf=False):
        line = f":{command} {message}"
        for value in self.server.clients.values():
            if channel in value.joinedChannels and (value != self or includeSelf):
                value.message(line)

    def message(self, msg):
        """
        Add a message (basic string) to client buffer.
        This is the lowest possible level.

        :param msg: message to add
        :return:
        """
        self.__writebuffer += msg + "\r\n"

    def writeBufferSize(self) -> int:
        """
        Return this client's write buffer size

        :return: write buffer size
        """
        return len(self.__writebuffer)

    def reply(self, msg: str) -> None:
        """
        Add an IRC-like message to client buffer.

        :param msg: message (without IRC stuff)
        :return:
        """
        self.message(f":{self.server.host} {msg}")

    def replyCode(
        self,
        code: int,
        message: str,
        nickname: str = "",
        channel: str = "",
    ) -> None:
        """
        Add an IRC-like message to client buffer with code

        :param code: response code
        :param message: response message
        :param nickname: receiver nickname
        :param channel: optional
        :return:
        """
        if nickname == "":
            nickname = self.IRCUsername
        if channel != "":
            channel = " " + channel
        self.reply(f"{code:03d} {nickname}{channel} :{message}")

    def reply403(self, channel: str) -> None:
        """
        Add a 403 reply (no such channel) to client buffer.

        :param channel:
        :return:
        """
        self.replyCode(403, f"{channel} :No such channel")

    def reply461(self, command: str) -> None:
        """
        Add a 461 reply (not enough parameters) to client buffer

        :param command: name of the command that had not enough parameters
        :return:
        """
        self.replyCode(403, f"{command} :Not enough parameters")

    def disconnect(self, quitmsg: str = "Client quit", callLogout: bool = True) -> None:
        """
        Disconnects this client from the IRC server

        :param quitmsg: IRC quit message. Default: 'Client quit'
        :param callLogout: if True, call logoutEvent on bancho
        :return:
        """
        # Send error to client and close socket
        self.message(f"ERROR :{quitmsg}")
        self.socket.close()

        logger.info(
            "IRC client disconnected",
            extra={
                "ip": self.ip,
                "port": self.port,
                "quit_msg": quitmsg,
            },
        )

        # Remove socket from server
        self.server.removeClient(self, quitmsg)

        # Bancho logout
        if callLogout and self.banchoUsername != "":
            chat.IRCDisconnect(self.IRCUsername)

    def readSocket(self) -> None:
        """
        Read data coming from this client socket

        :return:
        """
        try:
            # Try to read incoming data from socket
            data = self.socket.recv(2**10)
            logger.debug(
                "IRC client data received",
                extra={
                    "ip": self.ip,
                    "port": self.port,
                    "quit_msg": data,
                },
            )
            quitmsg = "EOT"
        except OSError as x:
            # Error while reading data, this client will be disconnected
            data = b""
            quitmsg = x

        if data:
            # Parse received data if needed
            self.__readbuffer += data.decode("latin_1")
            self.parseBuffer()
            self.__timestamp = time.time()
            self.__sentPing = False
        else:
            # No data, disconnect this socket
            self.disconnect(quitmsg)

    def parseBuffer(self) -> None:
        """
        Parse self.__readbuffer, get command, arguments and call its handler

        :return:
        """
        # Get lines from buffer
        lines = self.__linesep_regexp.split(self.__readbuffer)
        self.__readbuffer = lines[-1]
        lines = lines[:-1]

        # Process every line
        for line in lines:
            if not line:
                # Empty line. Ignore.
                continue

            # Get arguments
            x = line.split(" ", 1)

            # Command is the first argument, always uppercase
            command = x[0].upper()

            if len(x) == 1:
                # Command only, no arguments
                arguments = []
            else:
                # We have some arguments
                # Weird sorcery
                if len(x[1]) > 0 and x[1][0] == ":":
                    arguments = [x[1][1:]]
                else:
                    y = x[1].split(" :", 1)
                    arguments = y[0].split()
                    if len(y) == 2:
                        arguments.append(y[1])

            # Handle command with its arguments
            self.__handleCommand(command, arguments)

    def writeSocket(self) -> None:
        """
        Write buffer to socket

        :return:
        """
        try:
            sent = self.socket.send(self.__writebuffer.encode())
            logger.debug(
                "IRC client data transmitted",
                extra={
                    "ip": self.ip,
                    "port": self.port,
                    "quit_msg": self.__writebuffer[:sent],
                },
            )
            self.__writebuffer = self.__writebuffer[sent:]
        except OSError as x:
            self.disconnect(str(x))

    def checkAlive(self) -> None:
        """
        Check if this client is still connected.
        If the client is dead, disconnect it.

        :return:
        """
        now = time.time()
        if self.__timestamp + 180 < now:
            self.disconnect("ping timeout")
            return
        if not self.__sentPing and self.__timestamp + 90 < now:
            if self.__handleCommand == self.mainHandler:
                # Registered.
                self.message(f"PING :{self.server.host}")
                self.__sentPing = True
            else:
                # Not registered.
                self.disconnect("ping timeout")

    def sendLusers(self) -> None:
        """
        Send lusers response to this client

        :return:
        """
        self.replyCode(
            251,
            f"There are {len(osuToken.get_token_ids())} users and 0 services on 1 server",
        )

    def sendMotd(self) -> None:
        """
        Send MOTD to this client

        :return:
        """
        self.replyCode(375, f"- {self.server.host} Message of the day - ")
        if len(self.server.motd) == 0:
            self.replyCode(422, "MOTD File is missing")
        else:
            for i in self.server.motd:
                self.replyCode(372, f"- {i}")
        self.replyCode(376, "End of MOTD command")

    """""" """
    HANDLERS
    """ """"""

    def dummyHandler(self, command: str, arguments: list[str]) -> None:
        pass

    def passHandler(self, command: str, arguments: list[str]) -> None:
        """PASS command handler"""
        if command == "PASS":
            if len(arguments) == 0:
                self.reply461("PASS")
            else:
                # IRC token check
                m = hashlib.md5()
                m.update(arguments[0].encode("utf-8"))
                tokenHash = m.hexdigest()
                supposedUser = glob.db.fetch(
                    "SELECT users.username, users.id FROM users LEFT JOIN irc_tokens ON users.id = irc_tokens.userid WHERE irc_tokens.token = %s LIMIT 1",
                    [tokenHash],
                )
                if supposedUser:
                    self.supposedUsername = chat.fixUsernameForIRC(
                        supposedUser["username"],
                    )
                    self.supposedUserID = supposedUser["id"]
                    self.__handleCommand = self.registerHandler
                else:
                    # Wrong IRC Token
                    self.reply("464 :Password incorrect")
        elif command == "QUIT":
            self.disconnect()

    def registerHandler(self, command: str, arguments: list[str]) -> None:
        """NICK and USER commands handler"""
        if command == "NICK":
            if len(arguments) < 1:
                self.reply("431 :No nickname given")
                return
            nick = arguments[0]

            # Make sure this is the first time we set our nickname
            if self.IRCUsername != "":
                self.reply("432 * %s :Erroneous nickname" % nick)
                return

            # Make sure the IRC token was correct:
            # (self.supposedUsername is already fixed for IRC)
            if nick.lower() != self.supposedUsername.lower():
                self.reply("464 :Password incorrect")
                return

            # Make sure that the user is not banned/restricted:
            if not userUtils.isAllowed(self.supposedUserID):
                self.reply("465 :You're banned")
                return

            # Make sure we are not connected to Bancho
            token = tokenList.getTokenFromUsername(
                chat.fixUsernameForBancho(nick),
                ignoreIRC=True,
            )
            if token:
                self.reply(f"433 * {nick} :Nickname is already in use")
                return

            # Everything seems fine, set username (nickname)
            self.IRCUsername = nick  # username for IRC
            self.banchoUsername = chat.fixUsernameForBancho(
                self.IRCUsername,
            )  # username for bancho

            # Disconnect other IRC clients from the same user
            for value in self.server.clients.values():
                if (
                    value.IRCUsername.lower() == self.IRCUsername.lower()
                    and value != self
                ):
                    value.disconnect(quitmsg="Connected from another client")
                    return
        elif command == "USER":
            # Ignore USER command, we use nickname only
            return
        elif command == "QUIT":
            # Disconnect if we have received a QUIT command
            self.disconnect()
            return
        else:
            # Ignore any other command while logging in
            return

        # If we now have a valid username, connect to bancho and send IRC welcome stuff
        if self.IRCUsername != "":
            # Bancho connection
            chat.IRCConnect(self.banchoUsername)

            # IRC reply
            self.replyCode(1, "Welcome to the Internet Relay Network")
            self.replyCode(
                2,
                f"Your host is {self.server.host}, running version bancho-service",
            )
            self.replyCode(3, "This server was created since the beginning")
            self.replyCode(4, f"{self.server.host} bancho-service o o")
            self.sendLusers()
            self.sendMotd()
            self.__handleCommand = self.mainHandler

    def quitHandler(self, _, arguments: list[str]) -> None:
        """QUIT command handler"""
        self.disconnect(self.IRCUsername if len(arguments) < 1 else arguments[0])

    def joinHandler(self, _, arguments: list[str]) -> None:
        """JOIN command handler"""
        if len(arguments) < 1:
            self.reply461("JOIN")
            return

        # Get bancho token object
        token = tokenList.getTokenFromUsername(self.banchoUsername)
        if token is None:
            return

        # TODO: Part all channels
        if arguments[0] == "0":
            """for (channelname, channel) in self.channels.items():
                self.message_channel(channel, "PART", channelname, True)
                self.channel_log(channel, "left", meta=True)
                server.remove_member_from_channel(self, channelname)
            self.channels = {}
            return"""
            return

        # Get channels to join list
        channel_names = arguments[0].split(",")

        for channel_name in channel_names:
            # Make sure we are not already in that channel
            # (we already check this bancho-side, but we need to do it
            # also here k maron)
            if channel_name.lower() in token.joinedChannels:
                continue

            # Attempt to join the channel
            response = chat.IRCJoinChannel(self.banchoUsername, channel_name)
            if response == 0:
                # Joined successfully
                self.joinedChannels.append(channel_name)

                # Let everyone in this channel know that we've joined
                self.messageChannel(
                    channel_name,
                    f"{self.IRCUsername} JOIN",
                    channel_name,
                    includeSelf=True,
                )

                # Send channel description (topic)
                channel = channelList.getChannel(channel_name)
                if channel is None:
                    self.reply403(channel_name)
                    continue

                if channel["description"] == "":
                    self.replyCode(331, "No topic is set", channel=channel_name)
                else:
                    self.replyCode(332, channel["description"], channel=channel_name)

                # Build connected users list
                if f"chat/{channel_name}" not in streamList.getStreams():
                    self.reply403(channel_name)
                    continue
                users = stream.getClients(f"chat/{channel_name}")
                usernames = []
                for user in users:
                    token = osuToken.get_token(user)
                    if token is None:
                        continue
                    usernames.append(
                        chat.fixUsernameForIRC(token["username"]),
                    )
                usernames = " ".join(usernames)

                # Send IRC users list
                self.replyCode(353, usernames, channel=f"= {channel_name}")
                self.replyCode(366, "End of NAMES list", channel=channel_name)
            elif response == 403:
                # Channel doesn't exist (or no read permissions)
                self.reply403(channel_name)
                continue

    def partHandler(self, _, arguments: list[str]) -> None:
        """PART command handler"""
        if len(arguments) < 1:
            self.reply461("PART")
            return

        # Get bancho token object
        token = tokenList.getTokenFromUsername(self.banchoUsername)
        if token is None:
            return

        # Get channels to part list
        channels = arguments[0].split(",")

        for channel in channels:
            # Make sure we in that channel
            # (we already check this bancho-side, but we need to do it
            # also here k maron)
            if channel.lower() not in osuToken.get_joined_channels(token["token_id"]):
                continue

            # Attempt to part the channel
            response = chat.IRCPartChannel(self.banchoUsername, channel)
            if response == 0:
                # No errors, remove channel from joinedChannels
                self.joinedChannels.remove(channel)
            elif response == 403:
                self.reply403(channel)
            elif response == 442:
                self.replyCode(442, "You're not on that channel", channel=channel)

    def noticePrivmsgHandler(self, command: str, arguments: list[str]) -> None:
        """NOTICE and PRIVMSG commands handler (same syntax)"""
        # Syntax check
        if len(arguments) == 0:
            self.replyCode(411, f"No recipient given ({command})")
            return
        if len(arguments) == 1:
            self.replyCode(412, "No text to send")
            return
        recipientIRC = arguments[0]
        message = arguments[1]

        # Send the message to bancho and reply
        if not recipientIRC.startswith("#"):
            recipientBancho = chat.fixUsernameForBancho(recipientIRC)
        else:
            recipientBancho = recipientIRC
        response = chat.sendMessage(
            self.banchoUsername,
            recipientBancho,
            message,
            toIRC=False,
        )
        if response == 404:
            self.replyCode(404, "Cannot send to channel", channel=recipientIRC)
            return
        elif response == 403:
            self.replyCode(403, "No such channel", channel=recipientIRC)
            return
        elif response == 401:
            self.replyCode(401, "No such nick/channel", channel=recipientIRC)
            return

        # Send the message to IRC and bancho
        if recipientIRC.startswith("#"):
            # Public message (IRC)
            if recipientIRC not in channelList.getChannelNames():
                self.replyCode(401, "No such nick/channel", channel=recipientIRC)
                return
            for value in self.server.clients.values():
                if recipientIRC in value.joinedChannels and value != self:
                    value.message(
                        f":{self.IRCUsername} PRIVMSG {recipientIRC} :{message}",
                    )
        else:
            # Private message (IRC)
            for value in self.server.clients.values():
                if value.IRCUsername == recipientIRC:
                    value.message(
                        f":{self.IRCUsername} PRIVMSG {recipientIRC} :{message}",
                    )

    def motdHandler(self, command: str, arguments: list[str]) -> None:
        """MOTD command handler"""
        self.sendMotd()

    def lusersHandler(self, command: str, arguments: list[str]) -> None:
        """LUSERS command handler"""
        self.sendLusers()

    def pingHandler(self, _, arguments: list[str]) -> None:
        """PING command handler"""
        if len(arguments) < 1:
            self.replyCode(409, "No origin specified")
            return
        self.reply(f"PONG {self.server.host} :{arguments[0]}")

    def pongHandler(self, command: str, arguments: list[str]) -> None:
        """(fake) PONG command handler"""

    def awayHandler(self, _, arguments: list[str]) -> None:
        """AWAY command handler"""
        response = chat.IRCAway(self.banchoUsername, " ".join(arguments))
        self.replyCode(
            response,
            "You are no longer marked as being away"
            if response == 305
            else "You have been marked as being away",
        )

    def mainHandler(self, command: str, arguments: list[str]) -> None:
        """
        Handler for post-login commands
        """
        handlers = {
            "AWAY": self.awayHandler,
            # "ISON": ison_handler,
            "JOIN": self.joinHandler,
            # "LIST": list_handler,
            "LUSERS": self.lusersHandler,
            # "MODE": mode_handler,
            "MOTD": self.motdHandler,
            # "NICK": nick_handler,
            # "NOTICE": notice_and_privmsg_handler,
            "PART": self.partHandler,
            "PING": self.pingHandler,
            "PONG": self.pongHandler,
            "PRIVMSG": self.noticePrivmsgHandler,
            "QUIT": self.quitHandler,
            # "TOPIC": topic_handler,
            # "WALLOPS": wallops_handler,
            # "WHO": who_handler,
            # "WHOIS": whois_handler,
            "USER": self.dummyHandler,
        }
        try:
            handlers[command](command, arguments)
        except KeyError:
            self.replyCode(421, f"Unknown command ({command})")


class Server:
    def __init__(self, port: int):
        self.host = settings.IRC_HOSTNAME
        self.port = port
        self.clients = {}  # Socket - - > Client instance.
        self.motd = [
            "Welcome to bancho-service's embedded IRC server!",
            "This is a VERY simple IRC server and it's still in beta.",
            "Expect things to crash and not work as expected :(",
        ]

    def forceDisconnection(self, username: str, isBanchoUsername: bool = True) -> None:
        """
        Disconnect someone from IRC if connected

        :param username: victim
        :param isBanchoUsername: if True, username is a bancho username, else convert it to a bancho username
        :return:
        """
        for value in self.clients.values():
            if (value.IRCUsername == username and not isBanchoUsername) or (
                value.banchoUsername == username and isBanchoUsername
            ):
                value.disconnect(callLogout=False)
                break  # or dictionary changes size during iteration

    def banchoJoinChannel(self, username: str, channel: str) -> None:
        """
        Let every IRC client connected to a specific client know that 'username' joined the channel from bancho

        :param username: username of bancho user
        :param channel: joined channel name
        :return:
        """
        username = chat.fixUsernameForIRC(username)
        for value in self.clients.values():
            if channel in value.joinedChannels:
                value.message(f":{username} JOIN {channel}")

    def banchoPartChannel(self, username: str, channel: str) -> None:
        """
        Let every IRC client connected to a specific client know that 'username' parted the channel from bancho

        :param username: username of bancho user
        :param channel: joined channel name
        :return:
        """
        username = chat.fixUsernameForIRC(username)
        for value in self.clients.values():
            if channel in value.joinedChannels:
                value.message(f":{username} PART {channel}")

    def banchoMessage(self, fro: str, to: str, message: str) -> None:
        """
        Send a message to IRC when someone sends it from bancho

        :param fro: sender username
        :param to: receiver username
        :param message: text of the message
        :return:
        """
        fro = chat.fixUsernameForIRC(fro)
        to = chat.fixUsernameForIRC(to)
        if to.startswith("#"):
            # Public message
            for value in self.clients.values():
                if to in value.joinedChannels and value.IRCUsername != fro:
                    value.message(f":{fro} PRIVMSG {to} :{message}")
        else:
            # Private message
            for value in self.clients.values():
                if value.IRCUsername == to and value.IRCUsername != fro:
                    value.message(f":{fro} PRIVMSG {to} :{message}")

    def removeClient(self, client, _) -> None:
        """
        Remove a client from connected clients

        :param client: client object
        :return:
        """
        if client.socket in self.clients:
            del self.clients[client.socket]

    def start(self) -> None:
        """
        Start IRC server main loop

        :return:
        """
        serversocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        serversocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            serversocket.bind(("0.0.0.0", self.port))
        except OSError as exc:
            logger.debug(
                "IRC server could not bind port",
                exc_info=exc,
                extra={"port": self.port},
            )
            sys.exit(1)
        serversocket.listen(5)
        lastAliveCheck = time.time()

        # Main server loop
        while True:
            try:
                (iwtd, owtd, ewtd) = select.select(
                    [serversocket] + [x.socket for x in self.clients.values()],
                    [
                        x.socket
                        for x in self.clients.values()
                        if x.writeBufferSize() > 0
                    ],
                    [],
                    1,
                )

                # Handle incoming connections
                for x in iwtd:
                    if x in self.clients:
                        self.clients[x].readSocket()
                    else:
                        conn, addr = x.accept()
                        try:
                            self.clients[conn] = Client(self, conn)
                            logger.info(
                                "IRC connection accepted",
                                extra={"host": addr[0], "port": addr[1]},
                            )
                        except OSError:
                            try:
                                conn.close()
                            except:
                                pass

                # Handle outgoing connections
                for x in owtd:
                    if x in self.clients:  # client may have been disconnected
                        self.clients[x].writeSocket()

                # Make sure all IRC clients are still connected
                now = time.time()
                if lastAliveCheck + 10 < now:
                    for client in list(self.clients.values()):
                        client.checkAlive()
                    lastAliveCheck = now
            except Exception as exc:
                logger.error(
                    "Unknown error in IRC handling",
                    exc_info=exc,
                )


def main(port: int = 6667) -> None:
    """
    Create and start an IRC server

    :param port: IRC port. Default: 6667
    :return:
    """
    glob.ircServer = Server(port)
    glob.ircServer.start()
