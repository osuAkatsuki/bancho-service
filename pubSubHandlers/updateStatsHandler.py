from __future__ import annotations

from common.redis import generalPubSubHandler
from constants import serverPackets
from objects import osuToken, tokenList

class handler(generalPubSubHandler.generalPubSubHandler):
    def __init__(self):
        super().__init__()
        self.type = "int"

    def handle(self, userID):
        if (userID := super().parseData(userID)) is None:
            return

        if not (targetToken := tokenList.getTokenFromUserID(userID)):
            return

        osuToken.updateCachedStats(targetToken["token_id"])
        osuToken.enqueue(targetToken["token_id"], serverPackets.userStats(userID, force=True))
