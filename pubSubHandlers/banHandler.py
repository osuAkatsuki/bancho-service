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
        await user_utils.remove_first_place(userID)

        new_privileges = await user_utils.get_privileges(userID)

        all_user_tokens = await osuToken.get_all_tokens_by_user_id(userID)

        for token in all_user_tokens:
            maybe_token = await osuToken.update_token(
                token["token_id"], privileges=new_privileges,
            )
            assert maybe_token is not None
            token = maybe_token

            await osuToken.disconnectUserIfBanned(token["token_id"])
            await osuToken.notify_user_of_or_refresh_restriction_from_db(
                token["token_id"],
            )

        logger.info(
            "Successfully handled ban event for user",
            extra={"user_id": userID},
        )
