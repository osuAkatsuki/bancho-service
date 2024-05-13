from __future__ import annotations

from common.log import logger
from common.redis import generalPubSubHandler
from constants import serverPackets
from objects import osuToken
from objects import tokenList


class handler(generalPubSubHandler.generalPubSubHandler):
    def __init__(self) -> None:
        super().__init__()
        self.type = "int"

    async def handle(self, raw_data: bytes) -> None:
        if (userID := super().parseData(raw_data)) is None:
            return

        logger.info(
            "Handling update stats event for user",
            extra={"user_id": userID},
        )

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
