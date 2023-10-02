from __future__ import annotations

from common.log import logUtils as log
from constants import clientPackets
from constants import serverPackets
from objects import osuToken
from objects.osuToken import Token


async def handle(userToken: Token, rawPacketData: bytes):
    # Read userIDs list
    packetData = clientPackets.userPanelRequest(rawPacketData)

    # Process lists with length <= 32
    if len(packetData) > 256:
        log.warning("Received userPanelRequest with length > 256.")
        return

    for i in packetData["users"]:
        # Enqueue userpanel packets relative to this user
        log.debug(f"Sending panel for user {i}.")
        osuToken.enqueue(userToken["token_id"], serverPackets.userPanel(i))
