from __future__ import annotations
import logging

from common.redis import generalPubSubHandler
from objects import osuToken
from objects import tokenList


class handler(generalPubSubHandler.generalPubSubHandler):
    def __init__(self):
        super().__init__()
        self.type = "int"

    async def handle(self, userID):
        logging.info(
            "Handling update silence event for user",
            extra={"user_id": userID},
        )

        if (userID := super().parseData(userID)) is None:
            return

        if targetToken := await tokenList.getTokenFromUserID(userID):
            await osuToken.silence(targetToken["token_id"])

        logging.info(
            "Successfully handled update silence event for user",
            extra={"user_id": userID},
        )
