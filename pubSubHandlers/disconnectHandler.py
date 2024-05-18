from __future__ import annotations

from common.log import logger
from common.redis import generalPubSubHandler
from objects import osuToken
from objects import tokenList


class handler(generalPubSubHandler.generalPubSubHandler):
    def __init__(self) -> None:
        super().__init__()
        self.structure = {"userID": 0, "reason": ""}

    async def handle(self, raw_data: bytes) -> None:
        if (data := super().parseData(raw_data)) is None:
            return

        logger.info(
            "Handling disconnect event for user",
            extra={
                "user_id": data["userID"],
                "reason": data["reason"],
            },
        )

        if targetToken := await tokenList.getTokenFromUserID(data["userID"]):
            await osuToken.kick(targetToken["token_id"], data["reason"], "pubsub_kick")

        logger.info(
            "Successfully handled disconnect event for user",
            extra={
                "user_id": data["userID"],
                "reason": data["reason"],
            },
        )
