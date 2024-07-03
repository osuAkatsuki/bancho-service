#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import atexit
import logging
import os
import signal
import sys
import time
from types import FrameType

sys.path.insert(1, os.path.join(sys.path[0], "../.."))

import lifecycle
from common import exception_handling
from common.log import logger
from common.log import logging_config
from constants import CHATBOT_USER_ID
from events import logoutEvent
from objects import osuToken

CRON_RUN_INTERVAL = 10 * 60  # seconds

SHUTDOWN_EVENT: asyncio.Event | None = None


def handle_shutdown_event(signum: int, frame: FrameType | None) -> None:
    logging.info("Received shutdown signal", extra={"signum": signal.strsignal(signum)})
    if SHUTDOWN_EVENT is not None:
        SHUTDOWN_EVENT.set()


signal.signal(signal.SIGTERM, handle_shutdown_event)


async def _revoke_token_if_inactive(token: osuToken.Token) -> None:
    oldest_ping_time = int(time.time()) - CRON_RUN_INTERVAL

    if (
        token["ping_time"] < oldest_ping_time
        and token["user_id"] != CHATBOT_USER_ID
        and not token["tournament"]
    ):
        logger.info(
            "Timing out inactive bancho session",
            extra={
                "username": token["username"],
                "seconds_inactive": time.time() - token["ping_time"],
            },
        )

        await logoutEvent.handle(token)


async def _timeout_inactive_users() -> None:
    for token_id in await osuToken.get_token_ids():
        token = None
        try:
            token = await osuToken.get_token(token_id)
            if token is None:
                continue

            await _revoke_token_if_inactive(token)

        except Exception:
            logger.exception(
                "An error occurred while disconnecting a timed out client",
                extra={
                    "token_id": token_id,
                    "user_id": token["user_id"] if token else None,
                    "ping_time": token["ping_time"] if token else None,
                    "time_since_last_ping": (
                        time.time() - token["ping_time"] if token else None
                    ),
                    "tournament": token["tournament"] if token else None,
                },
            )


async def main() -> int:
    global SHUTDOWN_EVENT
    SHUTDOWN_EVENT = asyncio.Event()
    logger.info("Starting inactive token timeout loop")
    try:
        await lifecycle.startup()
        while not SHUTDOWN_EVENT.is_set():
            await _timeout_inactive_users()
            try:
                await asyncio.wait_for(
                    SHUTDOWN_EVENT.wait(),
                    timeout=CRON_RUN_INTERVAL,
                )
            except TimeoutError:
                pass
    finally:
        await lifecycle.shutdown()

    return 0


if __name__ == "__main__":
    logging_config.configure_logging()
    exception_handling.hook_exception_handlers()
    atexit.register(exception_handling.unhook_exception_handlers)
    try:
        exit_code = asyncio.run(main())
    except KeyboardInterrupt:
        exit_code = 0
    exit(exit_code)
