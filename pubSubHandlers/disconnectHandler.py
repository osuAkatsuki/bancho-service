from __future__ import annotations

import orjson

from common.log import logger
from common.redis.pubsubs import AbstractPubSubHandler
from objects import osuToken


class DisconnectPubSubHandler(AbstractPubSubHandler):
    async def handle(self, raw_data: bytes) -> None:
        data = orjson.loads(raw_data)
        assert data.keys() == {"userID", "reason"}

        logger.info(
            "Handling disconnect event for user",
            extra={
                "user_id": data["userID"],
                "reason": data["reason"],
            },
        )

        if targetToken := await osuToken.get_primary_token_by_user_id(data["userID"]):
            await osuToken.kick(targetToken["token_id"], data["reason"], "pubsub_kick")

        logger.info(
            "Successfully handled disconnect event for user",
            extra={
                "user_id": data["userID"],
                "reason": data["reason"],
            },
        )
