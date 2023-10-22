from __future__ import annotations

import logging

from common.redis import generalPubSubHandler
from objects import osuToken
from objects import tokenList


class handler(generalPubSubHandler.generalPubSubHandler):
    def __init__(self):
        super().__init__()
        self.structure = {"userID": 0, "reason": ""}

    async def handle(self, data):
        if (data := super().parseData(data)) is None:
            return

        logging.info(
            "Handling disconnect event for user",
            extra={
                "user_id": data["userID"],
                "reason": data["reason"],
            },
        )

        if targetToken := await tokenList.getTokenFromUserID(data["userID"]):
            await osuToken.kick(targetToken["token_id"], data["reason"], "pubsub_kick")

        logging.info(
            "Successfully handled disconnect event for user",
            extra={
                "user_id": data["userID"],
                "reason": data["reason"],
            },
        )
