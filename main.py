#!/usr/bin/env python3.9
from __future__ import annotations

import asyncio
import logging.config
import os
import signal
import sys
import traceback
from datetime import datetime
from typing import Optional

import redis.asyncio as redis
import tornado.gen
import tornado.httpserver
import tornado.ioloop
import tornado.web
import yaml

import settings
from handlers import apiFokabotMessageHandler
from handlers import apiIsOnlineHandler
from handlers import apiOnlineUsersHandler
from handlers import apiServerStatusHandler
from handlers import apiVerifiedStatusHandler
from handlers import mainHandler
from irc import ircserver
from objects import banchoConfig
from objects import channelList
from objects import fokabot
from objects import glob
from objects import streamList
from objects.dbPool import DBPool


def dump_thread_stacks():
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


def signal_handler(signum, frame):
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

        # Connect to db
        logging.info("Connecting to SQL")
        try:
            glob.db = DBPool()
            await glob.db.start()
        except:
            logging.exception("Error connecting to sql")
            raise

        # Connect to redis
        logging.info("Connecting to redis")
        try:
            glob.redis = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                password=settings.REDIS_PASS,
            )
            await glob.redis.ping()
        except:
            logging.exception("Error connecting to redis")
            raise

        # Load bancho_settings
        logging.info("Loading bancho settings")
        try:
            glob.banchoConf = banchoConfig.banchoConfig()
            await glob.banchoConf.loadSettings()
        except:
            logging.exception("Error loading bancho settings")
            raise

        # fetch privilege groups into memory
        # TODO: this is an optimization because ripple previously
        # fetched this so frequently. this is not robust as privilege
        # groups may change during runtime.
        glob.groupPrivileges = {
            row["name"].lower(): row["privileges"]
            for row in (
                await glob.db.fetchAll(
                    "SELECT name, privileges FROM privileges_groups",
                )
                or []
            )
        }

        await channelList.loadChannels()

        # Initialize stremas
        await streamList.add("main")
        await streamList.add("lobby")

        logging.info(
            "Connecting the in-game chat bot",
            extra={"bot_name": glob.BOT_NAME},
        )
        await fokabot.connect()

        if not settings.LOCALIZE_ENABLE:
            logging.info("User localization is disabled")

        if not settings.APP_GZIP:
            logging.info("Gzip compression is disabled")

        if settings.DEBUG:
            logging.info("Server running in debug mode")

        # # start irc server if configured
        if settings.IRC_ENABLE:
            logging.info(
                "IRC server listening on tcp port",
                extra={"port": settings.IRC_PORT},
            )
            asyncio.create_task(ircserver.main(port=settings.IRC_PORT))

        # Start the HTTP server
        API_ENDPOINTS = [
            (r"/", mainHandler.handler),
            (r"/api/v1/isOnline", apiIsOnlineHandler.handler),
            (r"/api/v1/onlineUsers", apiOnlineUsersHandler.handler),
            (r"/api/v1/serverStatus", apiServerStatusHandler.handler),
            (r"/api/v1/verifiedStatus", apiVerifiedStatusHandler.handler),
            (r"/api/v1/fokabotMessage", apiFokabotMessageHandler.handler),
        ]
        logging.info("Starting HTTP server")
        glob.application = tornado.web.Application(API_ENDPOINTS)
        http_server = tornado.httpserver.HTTPServer(glob.application)
        http_server.listen(settings.APP_PORT)
        logging.info(
            "HTTP server listening for clients",
            extra={
                "port": settings.APP_PORT,
                "endpoints": [e[0] for e in API_ENDPOINTS],
            },
        )
        shutdown_event = asyncio.Event()
        await shutdown_event.wait()
    finally:
        logging.info("Shutting down all services")

        if http_server is not None:
            logging.info("Closing HTTP listener")
            http_server.stop()
            logging.info("Closed HTTP listener")

            logging.info("Closing HTTP connections")
            # Allow grace period for ongoing connections to finish
            await asyncio.wait_for(
                http_server.close_all_connections(),
                timeout=settings.SHUTDOWN_HTTP_CONNECTION_TIMEOUT,
            )
            logging.info("Closed HTTP connections")

        # TODO: we can be more graceful with this one, but p3
        if settings.IRC_ENABLE:
            logging.info("Closing IRC server")
            glob.ircServer.close()
            logging.info("Closed IRC server")

        logging.info("Closing connection to redis")
        await glob.redis.aclose()
        logging.info("Closed connection to redis")

        logging.info("Closing connection(s) to MySQL")
        await glob.db.stop()
        logging.info("Closed connection(s) to MySQL")

        logging.info("Disconnecting from IRC")
        await fokabot.disconnect()
        logging.info("Disconnected from IRC")

        logging.info("Goodbye!")

    return 0


def configure_logging() -> None:
    with open("logging.yaml") as f:
        config = yaml.safe_load(f.read())
        logging.config.dictConfig(config)


if __name__ == "__main__":
    configure_logging()
    try:
        exit_code = asyncio.run(main())
    except KeyboardInterrupt:
        exit_code = 0

    exit(exit_code)
