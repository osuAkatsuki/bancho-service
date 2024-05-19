from __future__ import annotations

from common.log import logger
from common.redis.pubsubs import AbstractPubSubHandler
from objects import osuToken


class UpdateSilencePubSubHandler(AbstractPubSubHandler):
    async def handle(self, raw_data: bytes) -> None:
        userID = int(raw_data.decode("utf-8"))

        logger.info(
            "Handling update silence event for user",
            extra={"user_id": userID},
        )

        if targetToken := await osuToken.get_token_by_user_id(userID):
            await osuToken.silence(targetToken["token_id"])

        logger.info(
            "Successfully handled update silence event for user",
            extra={"user_id": userID},
        )
