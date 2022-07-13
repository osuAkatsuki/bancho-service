from common.log import logUtils as log
from constants import clientPackets, exceptions
from objects import glob
from objects.osuToken import token


def handle(userToken: token, rawPacketData: bytes):
    try:
        # Start spectating packet
        packetData = clientPackets.startSpectating(rawPacketData)

        # If the user id is less than 0, treat this as a stop spectating packet
        if packetData["userID"] < 0:
            userToken.stopSpectating()
            return

        # Get host token
        targetToken = glob.tokens.getTokenFromUserID(packetData["userID"])
        if targetToken is None:
            raise exceptions.tokenNotFoundException

        # Start spectating new user
        userToken.startSpectating(targetToken)
    except exceptions.tokenNotFoundException:
        # Stop spectating if token not found
        log.warning("Spectator start: token not found.")
        userToken.stopSpectating()
