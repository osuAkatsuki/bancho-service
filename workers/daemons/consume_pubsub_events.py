from __future__ import annotations

import logging
import os
import sys

sys.path.insert(1, os.path.join(sys.path[0], "../../.."))

from common.redis import pubSub
from common.redis.generalPubSubHandler import generalPubSubHandler
from objects import glob
from pubSubHandlers import banHandler
from pubSubHandlers import changeUsernameHandler
from pubSubHandlers import disconnectHandler
from pubSubHandlers import notificationHandler
from pubSubHandlers import unbanHandler
from pubSubHandlers import updateSilenceHandler
from pubSubHandlers import updateStatsHandler
from pubSubHandlers import wipeHandler


async def consume_pubsub_events() -> None:
    # Connect to pubsub channels
    PUBSUB_HANDLERS: dict[str, generalPubSubHandler] = {
        "peppy:ban": banHandler.handler(),
        "peppy:unban": unbanHandler.handler(),
        "peppy:silence": updateSilenceHandler.handler(),
        "peppy:disconnect": disconnectHandler.handler(),
        "peppy:notification": notificationHandler.handler(),
        "peppy:change_username": changeUsernameHandler.handler(),
        "peppy:update_cached_stats": updateStatsHandler.handler(),
        "peppy:wipe": wipeHandler.handler(),
        # TODO: support this?
        # "peppy:reload_settings": (
        #     lambda x: x == b"reload" and await glob.banchoConf.reload()
        # ),
    }
    logging.info(
        "Starting pubsub listener",
        extra={"handlers": list(PUBSUB_HANDLERS)},
    )
    pubsub_listener = pubSub.listener(
        redis_connection=glob.redis,
        handlers=PUBSUB_HANDLERS,
    )
    await pubsub_listener.run()
