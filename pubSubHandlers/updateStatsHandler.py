from __future__ import annotations

from common.log import logger
from common.redis import generalPubSubHandler
from constants import serverPackets
from objects import osuToken
from objects import tokenList


class handler(generalPubSubHandler.generalPubSubHandler):
    def __init__(self):
        super().__init__()
        self.type = "int"

    async def handle(self, userID):
        logger.info(
            "Handling update stats event for user",
            extra={"user_id": userID},
        )

        if (userID := super().parseData(userID)) is None:
            return

        if not (targetToken := await tokenList.getTokenFromUserID(userID)):
            logger.error(
                "Failed to find user by id in update stats pubsub handler",
                extra={"user_id": userID},
            )
            return

        await osuToken.updateCachedStats(targetToken["token_id"])
        await osuToken.enqueue(
            targetToken["token_id"],
            await serverPackets.userStats(userID, force=True),
        )

        logger.info(
            "Successfully handled update stats event for user",
            extra={"user_id": userID},
        )
