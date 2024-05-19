#!/usr/bin/env python3.9
from __future__ import annotations

import asyncio
import atexit
import os
import signal
import sys
import traceback
from datetime import datetime
from types import FrameType
from typing import Optional

import tornado.gen
import tornado.httpserver
import tornado.ioloop
import tornado.web

import lifecycle
import settings
from common import exception_handling
from common.log import logger
from common.log import logging_config
from constants import CHATBOT_USER_NAME
from handlers import apiChatbotMessageHandler
from handlers import apiIsOnlineHandler
from handlers import apiOnlineUsersHandler
from handlers import apiServerStatusHandler
from handlers import apiVerifiedStatusHandler
from handlers import mainHandler
from objects import channelList
from objects import chatbot
from objects import glob
from objects import streamList


def dump_thread_stacks() -> None:
    try:
        os.mkdir("stacktraces")
    except FileExistsError:
        pass
    filename = f"{settings.APP_PORT}-{datetime.now().isoformat()}.txt"
    with open(f"stacktraces/{filename}", "w") as f:
        for thread_id, stack in sys._current_frames().items():
            print(f"Thread ID: {thread_id}", file=f)
            traceback.print_stack(stack, file=f)
            print("\n", file=f)


def signal_handler(signum: int, frame: Optional[FrameType] = None) -> None:
    dump_thread_stacks()
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    signal.default_int_handler(signum, frame)


signal.signal(signal.SIGINT, signal_handler)


async def main() -> int:
    http_server: Optional[tornado.httpserver.HTTPServer] = None
    try:
        # TODO: do we need this anymore now with stateless design?
        # (not using filesystem anymore for things like .data/)
        os.chdir(os.path.dirname(os.path.realpath(__file__)))

        await lifecycle.startup()

        if settings.MASTER_PROCESS:
            await channelList.loadChannels()

            # Initialize stremas
            await streamList.add("main")
            await streamList.add("lobby")

            logger.info(
                "Connecting the in-game chat bot",
                extra={"bot_name": CHATBOT_USER_NAME},
            )

            await chatbot.connect()

        # Start the HTTP server
        API_ENDPOINTS = [
            (r"/", mainHandler.handler),
            (r"/api/v1/isOnline", apiIsOnlineHandler.handler),
            (r"/api/v1/onlineUsers", apiOnlineUsersHandler.handler),
            (r"/api/v1/serverStatus", apiServerStatusHandler.handler),
            (r"/api/v1/verifiedStatus", apiVerifiedStatusHandler.handler),
            # XXX: "fokabot" for legacy reasons
            (r"/api/v1/fokabotMessage", apiChatbotMessageHandler.handler),
        ]
        logger.info("Starting HTTP server")
        glob.application = tornado.web.Application(
            handlers=API_ENDPOINTS,  # type: ignore[arg-type]
        )
        http_server = tornado.httpserver.HTTPServer(glob.application)
        http_server.listen(settings.APP_PORT)
        logger.info(
            f"HTTP server listening for clients on port {settings.APP_PORT}",
            extra={
                "port": settings.APP_PORT,
                "endpoints": [e[0] for e in API_ENDPOINTS],
            },
        )
        shutdown_event = asyncio.Event()
        await shutdown_event.wait()
    finally:
        logger.info("Shutting down all services")

        if http_server is not None:
            logger.info("Closing HTTP listener")
            http_server.stop()
            logger.info("Closed HTTP listener")

            logger.info("Closing HTTP connections")
            # Allow grace period for ongoing connections to finish
            await asyncio.wait_for(
                http_server.close_all_connections(),
                timeout=settings.SHUTDOWN_HTTP_CONNECTION_TIMEOUT,
            )
            logger.info("Closed HTTP connections")

        if settings.MASTER_PROCESS:
            logger.info("Disconnecting Chatbot")
            await chatbot.disconnect()
            logger.info("Disconnected Chatbot")

        await lifecycle.shutdown()

        logger.info("Goodbye!")

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
