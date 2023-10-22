from __future__ import annotations

import logging

from common.redis import generalPubSubHandler
from common.ripple import userUtils
from objects import osuToken
from objects import tokenList


class handler(generalPubSubHandler.generalPubSubHandler):
    def __init__(self):
        super().__init__()
        self.type = "int"

    async def handle(self, userID):
        logging.info("Handling ban event for user", extra={"user_id": userID})

        if (userID := super().parseData(userID)) is None:
            logging.error(
                "User id not found for ban event pubsub handler",
                extra={"user_id": userID},
            )
            return

        userID = int(userID)

        await userUtils.removeFirstPlaces(userID)

        if not (targetToken := await tokenList.getTokenFromUserID(userID)):
            return

        targetToken["privileges"] = await userUtils.getPrivileges(userID)
        await osuToken.checkBanned(targetToken["token_id"])
        await osuToken.checkRestricted(targetToken["token_id"])

        logging.info(
            "Successfully handled ban event for user", extra={"user_id": userID}
        )
