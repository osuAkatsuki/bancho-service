from common.constants import actions, mods
from common.ripple import userUtils
from constants import clientPackets, serverPackets
from objects import glob

from common.log import logUtils as log

def handle(userToken, packetData):
    """ User is using Akatsuki's patcher and is trying to upgrade their connection. """

    log.info(f"{userToken.username} upgrading connection to protocol v{userToken.protocolVersion}.")
    packetData = clientPackets.changeProtocolVersion(packetData)
    userToken.protocolVersion = packetData["version"]
