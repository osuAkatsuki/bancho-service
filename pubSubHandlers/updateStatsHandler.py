from __future__ import annotations

from common.redis import generalPubSubHandler
from constants import serverPackets
from objects import glob


class handler(generalPubSubHandler.generalPubSubHandler):
    def __init__(self):
        super().__init__()
        self.type = "int"

    def handle(self, userID):
        if (userID := super().parseData(userID)) is None:
            return

        if not (targetToken := glob.tokens.getTokenFromUserID(userID)):
            return

        targetToken.updateCachedStats()
        force = True
        targetToken.enqueue(serverPackets.userStats(userID, force))
