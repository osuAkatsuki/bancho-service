from __future__ import annotations

from common.redis import generalPubSubHandler
from common.ripple import userUtils
from objects import osuToken
from objects import tokenList


class handler(generalPubSubHandler.generalPubSubHandler):
    def __init__(self):
        super().__init__()
        self.type = "int"

    async def handle(self, userID):
        if (userID := super().parseData(userID)) is None:
            return

        await userUtils.updateFirstPlaces(userID)

        if not (targetToken := await tokenList.getTokenFromUserID(userID)):
            return

        targetToken["privileges"] = await userUtils.getPrivileges(userID)
        await osuToken.checkBanned(targetToken["token_id"])
        await osuToken.checkRestricted(targetToken["token_id"])
