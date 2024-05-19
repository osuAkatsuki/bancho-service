from __future__ import annotations

from common.log import logger
from common.redis.pubsubs import AbstractPubSubHandler
from common.ripple import user_utils


class WipePubSubHandler(AbstractPubSubHandler):
    async def handle(self, raw_data: bytes) -> None:
        userID, rx, gm = (int(i) for i in raw_data.decode().split(","))

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
