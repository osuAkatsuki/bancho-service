from __future__ import annotations

from common.log import logUtils as log
from constants import clientPackets
from objects import osuToken

def handle(userToken: osuToken.Token, packetData):
    """User is using Akatsuki's patcher and is trying to upgrade their connection."""

    packetData = clientPackets.changeProtocolVersion(packetData)
    userToken["protocol_version"] = packetData["version"]
    osuToken.update_token(
        userToken["token_id"],
        protocol_version=userToken["protocol_version"],
    )

    log.info(
        f"{userToken['username']} upgraded connection to protocol v{userToken['protocol_version']}.",
    )
