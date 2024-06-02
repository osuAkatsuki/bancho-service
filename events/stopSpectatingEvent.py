from __future__ import annotations

from amplitude import BaseEvent

from common.log import logger
from constants import exceptions
from objects import glob
from objects import osuToken


async def handle(userToken: osuToken.Token, rawPacketData: bytes) -> None:
    try:
        # User must be spectating someone
        if userToken["spectating_user_id"] is None:
            return

        # Get host token
        targetToken = await osuToken.get_primary_token_by_user_id(
            userToken["spectating_user_id"],
        )
        if targetToken is None:
            raise exceptions.tokenNotFoundException

        await osuToken.stopSpectating(userToken["token_id"])

    except exceptions.tokenNotFoundException:
        # Stop spectating if token not found
        logger.warning(
            "Could not find the host token while stopping spectating",
            extra={
                "user_id": userToken["user_id"],
                "host_user_id": userToken["spectating_user_id"],
            },
        )

        # Set our spectating user to None
        await osuToken.update_token(
            userToken["token_id"],
            spectating_token_id=None,
            spectating_user_id=None,
        )
