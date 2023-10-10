import asyncio
import logging
from events import logoutEvent

from objects import osuToken
from objects.redisLock import redisLock
import time

OSU_MAX_PING_INTERVAL = 300  # seconds
CHATBOT_USER_ID = 999


async def timeout_inactive_users() -> None:
    logging.info("Starting user timeout loop")
    while True:
        timeout_limit = int(time.time()) - OSU_MAX_PING_INTERVAL

        for token_id in await osuToken.get_token_ids():
            async with redisLock(
                f"{osuToken.make_key(token_id)}:processing_lock",
            ):
                token = await osuToken.get_token(token_id)
                if token is None:
                    continue

                if (
                    token["ping_time"] < timeout_limit
                    and token["user_id"] != CHATBOT_USER_ID
                    and not token["irc"]
                    and not token["tournament"]
                ):
                    logging.warning(
                        "Timing out inactive bancho session",
                        extra={
                            "username": token["username"],
                            "seconds_inactive": time.time() - token["ping_time"],
                        },
                    )

                    try:
                        await logoutEvent.handle(token, _=None)
                    # except tokenNotFoundException:
                    #     pass  # lol
                    except Exception:
                        logging.exception(
                            "An error occurred while disconnecting a timed out client"
                        )

        await asyncio.sleep(OSU_MAX_PING_INTERVAL)
