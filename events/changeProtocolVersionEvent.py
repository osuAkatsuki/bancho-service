from __future__ import annotations

from common.log import logger
from constants import clientPackets
from objects import osuToken


def handle(userToken: osuToken.Token, packetData):
    """User is using Akatsuki's patcher and is trying to upgrade their connection."""

    initial_protocol_version = userToken["protocol_version"]
    packetData = clientPackets.changeProtocolVersion(packetData)
    userToken["protocol_version"] = packetData["version"]
    osuToken.update_token(
        userToken["token_id"],
        protocol_version=userToken["protocol_version"],
    )

    logger.info(
        "An osu! session upgraded their protocol version",
        extra={
            "user_id": userToken["user_id"],
            "username": userToken["username"],
            "old_version": initial_protocol_version,
            "new_version": userToken["protocol_version"],
        },
    )
