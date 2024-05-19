from __future__ import annotations

import orjson

from common.log import logger
from common.redis.pubsubs import AbstractPubSubHandler
from constants import serverPackets
from objects import osuToken


class NotificationPubSubHandler(AbstractPubSubHandler):
    async def handle(self, raw_data: bytes) -> None:
        data = orjson.loads(raw_data)
        assert data.keys() == {"userID", "message"}

        logger.info(
            "Handling notification event for user",
            extra={
                "user_id": data["userID"],
                "message": data["message"],
            },
        )

        if targetToken := await osuToken.get_token_by_user_id(data["userID"]):
            await osuToken.enqueue(
                targetToken["token_id"],
                serverPackets.notification(data["message"]),
            )

        logger.info(
            "Successfully handled notification event for user",
            extra={
                "user_id": data["userID"],
                "message": data["message"],
            },
        )
