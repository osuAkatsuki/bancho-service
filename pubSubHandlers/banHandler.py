from __future__ import annotations

from common.redis import generalPubSubHandler
from common.ripple import userUtils
from objects import glob


class handler(generalPubSubHandler.generalPubSubHandler):
    def __init__(self):
        super().__init__()
        self.type = "int"

    def handle(self, userID):
        if (userID := super().parseData(userID)) is None:
            return

        userUtils.removeFirstPlaces(userID)

        if not (targetToken := glob.tokens.getTokenFromUserID(userID)):
            return

        targetToken.privileges = userUtils.getPrivileges(userID)
        targetToken.checkBanned()
        targetToken.checkRestricted()
