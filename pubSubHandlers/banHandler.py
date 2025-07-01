from __future__ import annotations

from common.log import logger
from common.redis.pubsubs import AbstractPubSubHandler
from common.ripple import user_utils
from objects import osuToken


class BanPubSubHandler(AbstractPubSubHandler):
    async def handle(self, raw_data: bytes) -> None:
        userID = int(raw_data.decode("utf-8"))

        logger.info("Handling ban event for user", extra={"user_id": userID})

        # Remove the user from global, country and first place leaderboards
        await user_utils.remove_from_leaderboard(userID)
        await user_utils.remove_user_first_places(userID)

        if not (targetToken := await osuToken.get_token_by_user_id(userID)):
            return

        targetToken["privileges"] = await user_utils.get_privileges(userID)
        await osuToken.disconnectUserIfBanned(targetToken["token_id"])
        await osuToken.notifyUserOfRestrictionStatusChange(targetToken["token_id"])

        logger.info(
            "Successfully handled ban event for user",
            extra={"user_id": userID},
        )
