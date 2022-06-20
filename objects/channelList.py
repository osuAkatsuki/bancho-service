from cmyui.logging import Ansi, log
from constants import exceptions
from helpers import chatHelper as chat
from objects import channel, glob


class channelList:
    def __init__(self):
        self.channels = {}

    def loadChannels(self) -> None:
        """
        Load chat channels from db and add them to channels list
        :return:
        """
        # Get channels from DB
        channels = glob.db.fetchAll("SELECT * FROM bancho_channels")

        # Add each channel if needed
        for chan in channels:
            if chan["name"] not in self.channels:
                self.addChannel(
                    chan["name"],
                    chan["description"],
                    chan["public_read"] == 1,
                    chan["public_write"] == 1
                )

    def addChannel(
        self, name: str, description: str,
        publicRead: bool, publicWrite: bool,
        temp: bool = False, hidden: bool = False
    ) -> None:
        """
        Add a channel to channels list

        :param name: channel name
        :param description: channel description
        :param publicRead: if True, this channel can be read by everyone. If False, it can be read only by mods/admins
        :param publicWrite: same as public read, but regards writing permissions
        :param temp: if True, this channel will be deleted when there's no one in this channel
        :param hidden: if True, thic channel won't be shown in channels list
        :return:
        """
        glob.streams.add(f"chat/{name}")
        self.channels[name] = channel.channel(name, description, publicRead, publicWrite, temp, hidden)
        log(f'Created channel {name}.')

    def addTempChannel(self, name: str) -> None:
        """
        Add a temporary channel (like #spectator or #multiplayer), gets deleted when there's no one in the channel
        and it's hidden in channels list

        :param name: channel name
        :return: True if the channel was created, otherwise False
        """
        if name in self.channels:
            return False

        glob.streams.add(f"chat/{name}")
        self.channels[name] = channel.channel(
            name=name, description="Chat", publicRead=True,
            publicWrite=True, temp=True, hidden=True
        )

        log(f'Created temp channel {name}.')

    def addHiddenChannel(self, name: str) -> None:
        """
        Add a hidden channel. It's like a normal channel and must be deleted manually,
        but it's not shown in channels list.

        :param name: channel name
        :return: True if the channel was created, otherwise False
        """
        if name in self.channels:
            return False

        glob.streams.add(f"chat/{name}")
        self.channels[name] = channel.channel(
            name=name, description="Chat", publicRead=True,
            publicWrite=True, temp=False, hidden=True
        )

        log(f'Created hidden channel {name}.')

    def removeChannel(self, name: str) -> None:
        """
        Removes a channel from channels list

        :param name: channel name
        :return:
        """
        if name not in self.channels:
            log(f"{name} is not in channels list?", Ansi.LYELLOW)
            return

        #glob.streams.broadcast(f"chat/{name}", serverPackets.channelKicked(name))

        stream = glob.streams.getStream(f"chat/{name}")
        if stream:
            for token in stream.clients:
                if token in glob.tokens.tokens:
                    chat.partChannel(channel=name, token=glob.tokens.tokens[token], kick=True)

        glob.streams.dispose(f"chat/{name}")
        glob.streams.remove(f"chat/{name}")
        self.channels.pop(name)
        log(f'Removed channel {name}.')

    @staticmethod
    def getMatchIDFromChannel(chan: str) -> int:
        if not chan.lower().startswith("#multi_"):
            raise exceptions.wrongChannelException()

        parts = chan.lower().split("_")
        if len(parts) < 2 or not parts[1].isdigit():
            raise exceptions.wrongChannelException()

        matchID = int(parts[1])
        if matchID not in glob.matches.matches:
            raise exceptions.matchNotFoundException()

        return matchID

    @staticmethod
    def getSpectatorHostUserIDFromChannel(chan: str) -> int:
        if not chan.lower().startswith("#spect_"):
            raise exceptions.wrongChannelException()

        parts = chan.lower().split("_")
        if len(parts) < 2 or not parts[1].isdigit():
            raise exceptions.wrongChannelException()

        userID = int(parts[1])
        return userID
