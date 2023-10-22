from __future__ import annotations

import logging

from constants import clientPackets
from constants import serverPackets
from objects import osuToken
from objects.osuToken import Token


async def handle(userToken: Token, rawPacketData: bytes):
    # Read userIDs list
    packetData = clientPackets.userPanelRequest(rawPacketData)

    # Process lists with length <= 32
    if len(packetData) > 256:
        logging.warning(
            "Received userPanelRequest with length > 256",
            extra={
                "length": len(packetData),
                "user_id": userToken["user_id"],
            },
        )
        return

    for other_id in packetData["users"]:
        other_token = await osuToken.get_token_by_user_id(user_id=i)
        if other_token is None:
            logging.info(
                "Failed to find requested user when sending panel",
                extra={"user_id": other_id},
            )
            continue

        # Enqueue userpanel packets relative to this user
        logging.debug(
            "Sending panel for user",
            extra={"user_id": other_token["user_id"]},
        )
        await osuToken.enqueue(
            userToken["token_id"],
            await serverPackets.userPanel(other_token),
        )
