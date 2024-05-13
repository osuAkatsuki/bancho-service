from __future__ import annotations

from common.log import logger
from common.redis import generalPubSubHandler
from common.ripple import userUtils


class handler(generalPubSubHandler.generalPubSubHandler):
    def __init__(self):
        super().__init__()
        self.type = "int_list"

    async def handle(self, userID):
        logger.info(
            "Handling wipe event for user",
            extra={"user_id": userID},
        )

        userID, rx, gm = super().parseData(userID)
        if any(i is None for i in (userID, rx, gm)):
            return

        await userUtils.remove_first_place(userID, rx, gm)
        await userUtils.remove_from_specified_leaderboard(userID, gm, rx)

        logger.info(
            "Successfully handled wipe event for user",
            extra={"user_id": userID},
        )
