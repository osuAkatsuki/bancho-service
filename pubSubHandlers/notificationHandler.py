from __future__ import annotations

from common.log import logger
from common.redis import generalPubSubHandler
from constants import serverPackets
from objects import osuToken
from objects import tokenList


class handler(generalPubSubHandler.generalPubSubHandler):
    def __init__(self):
        super().__init__()
        self.structure = {"userID": 0, "message": ""}

    async def handle(self, data):
        if (data := super().parseData(data)) is None:
            return

        logger.info(
            "Handling notification event for user",
            extra={
                "user_id": data["userID"],
                "message": data["message"],
            },
        )

        if targetToken := await tokenList.getTokenFromUserID(data["userID"]):
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
