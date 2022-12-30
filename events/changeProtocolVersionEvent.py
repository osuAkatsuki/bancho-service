from __future__ import annotations

from common.log import logUtils as log
from constants import clientPackets


def handle(userToken: token, packetData):
    """User is using Akatsuki's patcher and is trying to upgrade their connection."""

    packetData = clientPackets.changeProtocolVersion(packetData)
    userToken.protocolVersion = packetData["version"]

    log.info(
        f"{userToken.username} upgraded connection to protocol v{userToken.protocolVersion}.",
    )
