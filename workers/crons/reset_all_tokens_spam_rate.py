#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import atexit
import logging
import os
import signal
import sys
from types import FrameType

sys.path.insert(1, os.path.join(sys.path[0], "../.."))

import lifecycle
from common import exception_handling
from common.log import logger
from common.log import logging_config
from objects import osuToken

# TODO: this work should be done JIT when a player sends a message
# and the cronjob/daemon strategy here should be completely removed

CRON_RUN_INTERVAL = 60  # seconds

SHUTDOWN_EVENT: asyncio.Event | None = None


def handle_shutdown_event(signum: int, frame: FrameType | None) -> None:
    logging.info("Received shutdown signal", extra={"signum": signal.strsignal(signum)})
    if SHUTDOWN_EVENT is not None:
        SHUTDOWN_EVENT.set()


signal.signal(signal.SIGTERM, handle_shutdown_event)


async def main() -> int:
    global SHUTDOWN_EVENT
    SHUTDOWN_EVENT = asyncio.Event()
    logger.info("Starting spam protection loop")
    try:
        await lifecycle.startup()
        while True:
            for token_id in await osuToken.get_token_ids():
                await osuToken.update_token(token_id, spam_rate=0)

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
