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
from objects import stream_messages
from objects import streamList

# TODO: this work should be done JIT when a player sends a message
# and the cronjob/daemon strategy here should be completely removed

FIVE_MINUTES = 5 * 60

SHUTDOWN_EVENT: asyncio.Event | None = None


def handle_shutdown_event(signum: int, frame: FrameType | None) -> None:
    logging.info("Received shutdown signal", extra={"signum": signal.strsignal(signum)})
    if SHUTDOWN_EVENT is not None:
        SHUTDOWN_EVENT.set()


signal.signal(signal.SIGTERM, handle_shutdown_event)


async def main() -> int:
    global SHUTDOWN_EVENT
    SHUTDOWN_EVENT = asyncio.Event()
    logger.info("Starting outdated stream message trim loop")
    try:
        await lifecycle.startup()
        while True:
            for stream_name in await streamList.getStreams():
                try:
                    five_minutes_ago = time.time() - FIVE_MINUTES
                    trimmed_messages = await stream_messages.trim_stream_messages(
                        stream_name,
                        min_id=f"{int(five_minutes_ago * 1000)}-0",
                    )
                    if trimmed_messages:
                        logger.info(
                            "Trimmed outdated stream messages",
                            extra={
                                "stream_name": stream_name,
                                "trimmed_messages": trimmed_messages,
                            },
                        )
                    await asyncio.wait_for(
                        SHUTDOWN_EVENT.wait(),
                        timeout=1,
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
