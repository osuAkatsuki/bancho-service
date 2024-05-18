from __future__ import annotations

from common.log import logger
from constants import exceptions
from constants import serverPackets
from objects import osuToken
from objects.osuToken import Token


async def handle(token: Token, rawPacketData: bytes) -> None:
    try:
        # We don't have the beatmap, we can't spectate
        if (
            token["spectating_token_id"] is None
            or token["spectating_token_id"] not in await osuToken.get_token_ids()
        ):
            raise exceptions.tokenNotFoundException()

        # Send the packet to host
        await osuToken.enqueue(
            token["spectating_token_id"],
            serverPackets.noSongSpectator(token["user_id"]),
        )
    except exceptions.tokenNotFoundException:
        # Stop spectating if token not found
        logger.warning("Spectator can't spectate: token not found.")
        await osuToken.stopSpectating(token["token_id"])
