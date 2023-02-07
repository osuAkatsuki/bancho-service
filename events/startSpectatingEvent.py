from __future__ import annotations

from common.log import logUtils as log
from constants import clientPackets
from constants import exceptions
from objects.osuToken import Token
from objects import osuToken, tokenList


def handle(userToken: Token, rawPacketData: bytes):
    try:
        # Start spectating packet
        packetData = clientPackets.startSpectating(rawPacketData)

        # If the user id is less than 0, treat this as a stop spectating packet
        if packetData["userID"] < 0:
            osuToken.stopSpectating(userToken["token_id"], )
            return

        # Get host token
        targetToken = tokenList.getTokenFromUserID(packetData["userID"])
        if targetToken is None:
            raise exceptions.tokenNotFoundException

        # Start spectating new user
        osuToken.startSpectating(userToken["token_id"], targetToken["token_id"])
    except exceptions.tokenNotFoundException:
        # Stop spectating if token not found
        log.warning("Spectator start: token not found.")
        osuToken.stopSpectating(userToken["token_id"], )
