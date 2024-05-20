from __future__ import annotations

from common.log import logger
from common.redis.pubsubs import AbstractPubSubHandler
from constants import serverPackets
from objects import osuToken


class UpdateStatsPubSubHandler(AbstractPubSubHandler):
    async def handle(self, raw_data: bytes) -> None:
        userID = int(raw_data.decode("utf-8"))

        logger.info(
            "Handling update stats event for user",
            extra={"user_id": userID},
        )

        if not (targetToken := await osuToken.get_primary_token_by_user_id(userID)):
            logger.error(
                "Failed to find user by id in update stats pubsub handler",
                extra={"user_id": userID},
            )
            return

        await osuToken.updateCachedStats(targetToken["token_id"])
        await osuToken.enqueue(
            targetToken["token_id"],
            await serverPackets.userStats(
                user_id=userID,
                allow_restricted_tokens=True,
            ),
        )

        logger.info(
            "Successfully handled update stats event for user",
            extra={"user_id": userID},
        )
