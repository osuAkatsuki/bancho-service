from __future__ import annotations

from common.redis import generalPubSubHandler
from constants import serverPackets
from objects import glob


class handler(generalPubSubHandler.generalPubSubHandler):
    def __init__(self):
        super().__init__()
        self.structure = {"userID": 0, "message": ""}

    def handle(self, data):
        if (data := super().parseData(data)) is None:
            return

        if targetToken := glob.tokens.getTokenFromUserID(data["userID"]):
            targetToken.enqueue(serverPackets.notification(data["message"]))
