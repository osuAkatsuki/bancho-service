from __future__ import annotations

from common.log import logger
from common.redis.pubsubs import AbstractPubSubHandler
from common.ripple import user_utils
from objects import osuToken


class UnbanPubSubHandler(AbstractPubSubHandler):
    async def handle(self, raw_data: bytes) -> None:
        userID = int(raw_data.decode("utf-8"))

        logger.info(
            "Handling unban event for user",
            extra={"user_id": userID},
        )

        await user_utils.recalculate_and_update_first_place_scores(userID)

        if not (targetToken := await osuToken.get_token_by_user_id(userID)):
            logger.error(
                "Failed to find user by id in update stats pubsub handler",
                extra={"user_id": userID},
            )
            return

        targetToken["privileges"] = await user_utils.get_privileges(userID)
        await osuToken.disconnectUserIfBanned(targetToken["token_id"])
        await osuToken.checkRestricted(targetToken["token_id"])

        logger.info(
            "Successfully handled unban event for user",
            extra={"user_id": userID},
        )
