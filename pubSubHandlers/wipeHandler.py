from __future__ import annotations

from common.redis import generalPubSubHandler
from common.ripple import userUtils


class handler(generalPubSubHandler.generalPubSubHandler):
    def __init__(self):
        super().__init__()
        self.type = "int_list"

    def handle(self, userID):
        userID, rx, gm = super().parseData(userID)
        if any(i is None for i in (userID, rx, gm)):
            return

        # TODO: update flame's cache and send gamemode on wipe.
        userUtils.removeFirstPlaces(userID, rx, gm)
