from __future__ import annotations

from constants import clientPackets
from objects import osuToken
from objects.osuToken import Token


async def handle(userToken: Token, rawPacketData: bytes):
    osuToken.update_token(
        userToken["token_id"],
        block_non_friends_dm=clientPackets.blockDM(rawPacketData)["value"] != 0,
    )
