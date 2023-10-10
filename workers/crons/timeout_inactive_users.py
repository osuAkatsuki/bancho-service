from __future__ import annotations

import asyncio
import logging
import time

from events import logoutEvent
from objects import osuToken
from objects.redisLock import redisLock

OSU_MAX_PING_INTERVAL = 300  # seconds
CHATBOT_USER_ID = 999


async def _maybe_timeout_inactive_user(token: osuToken.Token) -> None:
    timeout_limit = int(time.time()) - OSU_MAX_PING_INTERVAL

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

        await logoutEvent.handle(token, _=None)


async def timeout_inactive_users() -> None:
    logging.info("Starting user timeout loop")
    while True:
        for token_id in await osuToken.get_token_ids():
            token = None
            try:
                async with redisLock(
                    f"{osuToken.make_key(token_id)}:processing_lock",
                ):
                    token = await osuToken.get_token(token_id)
                    if token is None:
                        continue

                    await _maybe_timeout_inactive_user(token)

            except Exception:
                logging.exception(
                    "An error occurred while disconnecting a timed out client",
                    extra={
                        "token_id": token_id,
                        "user_id": token["user_id"] if token else None,
                        "ping_time": token["ping_time"] if token else None,
                        "time_since_last_ping": (
                            time.time() - token["ping_time"] if token else None
                        ),
                        "irc": token["irc"] if token else None,
                        "tournament": token["tournament"] if token else None,
                    },
                )

        await asyncio.sleep(OSU_MAX_PING_INTERVAL)
