from __future__ import annotations

from common.redis import generalPubSubHandler
from objects import glob


class handler(generalPubSubHandler.generalPubSubHandler):
    def __init__(self):
        super().__init__()
        self.type = "int"

    def handle(self, userID):
        if (userID := super().parseData(userID)) is None:
            return

        if targetToken := glob.tokens.getTokenFromUserID(userID):
            targetToken.silence()
