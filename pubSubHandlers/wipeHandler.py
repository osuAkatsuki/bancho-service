from __future__ import annotations

from common.log import logger
from common.redis import generalPubSubHandler
from common.ripple import user_utils


class handler(generalPubSubHandler.generalPubSubHandler):
    def __init__(self) -> None:
        super().__init__()
        self.type = "int_list"

    async def handle(self, raw_data: bytes) -> None:
        userID, rx, gm = super().parseData(raw_data)
        if any(i is None for i in (userID, rx, gm)):
            return

        logger.info(
            "Handling wipe event for user",
            extra={"user_id": userID},
        )

        await user_utils.remove_first_place(userID, rx, gm)
        await user_utils.remove_from_specified_leaderboard(userID, gm, rx)

        logger.info(
            "Successfully handled wipe event for user",
            extra={"user_id": userID},
        )
