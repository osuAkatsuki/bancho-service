from __future__ import annotations

from common.redis import generalPubSubHandler
from constants import serverPackets
from objects import osuToken
from objects import tokenList


class handler(generalPubSubHandler.generalPubSubHandler):
    def __init__(self):
        super().__init__()
        self.type = "int"

    async def handle(self, userID):
        if (userID := super().parseData(userID)) is None:
            return

        if not (targetToken := await tokenList.getTokenFromUserID(userID)):
            return

        await osuToken.updateCachedStats(targetToken["token_id"])
        await osuToken.enqueue(
            targetToken["token_id"],
            serverPackets.userStats(userID, force=True),
        )
