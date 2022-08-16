from constants import clientPackets

from common.log import logUtils as log

def handle(userToken, packetData):
    """ User is using Akatsuki's patcher and is trying to upgrade their connection. """

    packetData = clientPackets.changeProtocolVersion(packetData)
    userToken.protocolVersion = packetData["version"]

    log.info(f"{userToken.username} upgraded connection to protocol v{userToken.protocolVersion}.")
