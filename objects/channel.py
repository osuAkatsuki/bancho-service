from __future__ import annotations

import logging

from constants import exceptions
from objects import glob


class channel:
    __slots__ = (
        "name",
        "description",
        "publicRead",
        "publicWrite",
        "moderated",
        "temp",
        "hidden",
        "isSpecial",
        "clientName",
    )

    def __init__(
        self,
        name: str,
        description: str,
        publicRead: bool,
        publicWrite: bool,
        temp: bool,
        hidden: bool,
    ) -> None:
        """
        Create a new chat channel object

        :param name: channel name
        :param description: channel description
        :param publicRead: if True, this channel can be read by everyone. If False, it can be read only by mods/admins
        :param publicWrite: same as public read, but regards writing permissions
        :param temp: if True, this channel will be deleted when there's no one in this channel
        :param hidden: if True, thic channel won't be shown in channels list
        """
        self.name = name
        self.description = description
        self.publicRead = publicRead
        self.publicWrite = publicWrite
        self.moderated = False
        self.temp = temp
        self.hidden = hidden

        self.isSpecial = True
        if name.startswith("#spect_"):
            self.clientName = "#spectator"
        elif name.startswith("#multi_"):
            self.clientName = "#multiplayer"
        else:
            self.clientName = name
            self.isSpecial = False

        # Make Foka join the channel
        fokaToken = glob.tokens.getTokenFromUserID(999)
        if fokaToken:
            try:
                fokaToken.joinChannel(self)
            except exceptions.userAlreadyInChannelException:
                logging.warning(f"{glob.BOT_NAME} has already joined channel {name}")
