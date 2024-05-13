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
            logger.error(
                "Failed to find user by id in ban pubsub handler",
                extra={"raw_data": raw_data},
            )
            return

        userID = int(userID)

        logger.info("Handling ban event for user", extra={"user_id": userID})

        # Remove the user from global, country and first place leaderboards
        await user_utils.remove_from_leaderboard(userID)
        await user_utils.remove_first_place(userID)

        if not (targetToken := await tokenList.getTokenFromUserID(userID)):
            return

        targetToken["privileges"] = await user_utils.get_privileges(userID)
        await osuToken.disconnectUserIfBanned(targetToken["token_id"])
        await osuToken.checkRestricted(targetToken["token_id"])

        logger.info(
            "Successfully handled ban event for user",
            extra={"user_id": userID},
        )
