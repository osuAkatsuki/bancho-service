from __future__ import annotations

from common.log import logger
from common.redis import generalPubSubHandler
from common.ripple import user_utils
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
            "Handling unban event for user",
            extra={"user_id": userID},
        )

        await user_utils.recalculate_and_update_first_place_scores(userID)

        if not (targetToken := await tokenList.getTokenFromUserID(userID)):
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
