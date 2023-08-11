from __future__ import annotations

from common.redis import generalPubSubHandler
from objects import glob
from objects import osuToken
from objects import tokenList


class handler(generalPubSubHandler.generalPubSubHandler):
    def __init__(self):
        super().__init__()
        self.type = "int"

    def handle(self, userID):
        if (userID := super().parseData(userID)) is None:
            return

        if targetToken := tokenList.getTokenFromUserID(userID):
            osuToken.silence(targetToken["token_id"])
