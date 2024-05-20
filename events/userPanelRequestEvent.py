from __future__ import annotations

from common.log import logger
from constants import clientPackets
from constants import serverPackets
from objects import osuToken
from objects.osuToken import Token


async def handle(userToken: Token, rawPacketData: bytes) -> None:
    # Read userIDs list
    packetData = clientPackets.userPanelRequest(rawPacketData)

    # Process lists with length <= 32
    if len(packetData) > 256:
        logger.warning(
            "Received userPanelRequest with length > 256",
            extra={
                "length": len(packetData),
                "user_id": userToken["user_id"],
            },
        )
        return

    for user_id in packetData["users"]:
        # Enqueue userpanel packets relative to this user
        logger.debug("Sending panel for user", extra={"user_slot_num": user_id})
        await osuToken.enqueue(
            userToken["token_id"],
            await serverPackets.userPanel(user_id=user_id),
        )
