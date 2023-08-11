from __future__ import annotations

from common.redis import generalPubSubHandler
from objects import osuToken
from objects import tokenList


class handler(generalPubSubHandler.generalPubSubHandler):
    def __init__(self):
        super().__init__()
        self.structure = {"userID": 0, "reason": ""}

    def handle(self, data):
        if (data := super().parseData(data)) is None:
            return

        if targetToken := tokenList.getTokenFromUserID(data["userID"]):
            osuToken.kick(targetToken["token_id"], data["reason"], "pubsub_kick")
