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
from common.redis import pubSub
from common.redis.pubsubs import AbstractPubSubHandler
from objects import glob
from pubSubHandlers import banHandler
from pubSubHandlers import changeUsernameHandler
from pubSubHandlers import disconnectHandler
from pubSubHandlers import notificationHandler
from pubSubHandlers import unbanHandler
from pubSubHandlers import updateSilenceHandler
from pubSubHandlers import updateStatsHandler
from pubSubHandlers import wipeHandler

PUBSUB_HANDLERS: dict[str, AbstractPubSubHandler] = {
    "peppy:ban": banHandler.BanPubSubHandler(),
    "peppy:unban": unbanHandler.UnbanPubSubHandler(),
    "peppy:silence": updateSilenceHandler.UpdateSilencePubSubHandler(),
    "peppy:disconnect": disconnectHandler.DisconnectPubSubHandler(),
    "peppy:notification": notificationHandler.NotificationPubSubHandler(),
    "peppy:change_username": changeUsernameHandler.ChangeUsernamePubSubHandler(),
    "peppy:update_cached_stats": updateStatsHandler.UpdateStatsPubSubHandler(),
    "peppy:wipe": wipeHandler.WipePubSubHandler(),
}

SHUTDOWN_EVENT: asyncio.Event | None = None


def handle_shutdown_event(signum: int, frame: FrameType | None) -> None:
    logging.info("Received shutdown signal", extra={"signum": signal.strsignal(signum)})
    if SHUTDOWN_EVENT is not None:
        SHUTDOWN_EVENT.set()


signal.signal(signal.SIGTERM, handle_shutdown_event)


async def main() -> int:
    global SHUTDOWN_EVENT
    SHUTDOWN_EVENT = asyncio.Event()
    logger.info(
        "Starting pubsub listener",
        extra={"handlers": list(PUBSUB_HANDLERS)},
    )
    try:
        await lifecycle.startup()
        pubsub_listener = pubSub.listener(
            redis_connection=glob.redis,
            handlers=PUBSUB_HANDLERS,
        )
        pubsub = pubsub_listener.redis_connection.pubsub()

        channels = list(pubsub_listener.handlers.keys())
        await pubsub.subscribe(*channels)
        logger.info(
            "Subscribed to redis pubsub channels",
            extra={"channels": channels},
        )

        async for item in pubsub.listen():
            try:
                await pubsub_listener.processItem(item)
            except Exception:
                logger.exception(
                    "An error occurred while processing a pubsub item",
                    extra={"item": item},
                )

                if SHUTDOWN_EVENT.is_set():
                    break

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
