from __future__ import annotations

from common.log import logger
from common.redis import generalPubSubHandler
from common.ripple import userUtils
from objects import osuToken
from objects import tokenList


class handler(generalPubSubHandler.generalPubSubHandler):
    def __init__(self):
        super().__init__()
        self.type = "int"

    async def handle(self, userID):
        logger.info(
            "Handling unban event for user",
            extra={"user_id": userID},
        )

        if (userID := super().parseData(userID)) is None:
            return

        await userUtils.updateFirstPlaces(userID)

        if not (targetToken := await tokenList.getTokenFromUserID(userID)):
            logger.error(
                "Failed to find user by id in update stats pubsub handler",
                extra={"user_id": userID},
            )
            return

        targetToken["privileges"] = await userUtils.getPrivileges(userID)
        await osuToken.disconnectUserIfBanned(targetToken["token_id"])
        await osuToken.checkRestricted(targetToken["token_id"])

        logger.info(
            "Successfully handled unban event for user",
            extra={"user_id": userID},
        )
