from __future__ import annotations

from common.redis import generalPubSubHandler
from objects import glob


class handler(generalPubSubHandler.generalPubSubHandler):
    def __init__(self):
        super().__init__()
        self.structure = {"userID": 0, "reason": ""}

    def handle(self, data):
        if (data := super().parseData(data)) is None:
            return

        if targetToken := glob.tokens.getTokenFromUserID(data["userID"]):
            targetToken.kick(data["reason"], "pubsub_kick")
