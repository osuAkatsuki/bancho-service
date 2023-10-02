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

import psutil
import redis.asyncio as redis
import tornado.gen
import tornado.httpserver
import tornado.ioloop
import tornado.web
import yaml

import settings
from common.constants import bcolors
from common.ddog import datadogClient
from common.redis import pubSub
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
from objects import match
from objects import osuToken
from objects import streamList
from objects import tokenList
from objects.dbPool import DBPool
from pubSubHandlers import banHandler
from pubSubHandlers import changeUsernameHandler
from pubSubHandlers import disconnectHandler
from pubSubHandlers import notificationHandler
from pubSubHandlers import unbanHandler
from pubSubHandlers import updateSilenceHandler
from pubSubHandlers import updateStatsHandler
from pubSubHandlers import wipeHandler


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

        # set up datadog
        logging.info("Setting up datadog clients")
        try:
            if settings.DATADOG_ENABLE:
                glob.dog = datadogClient.datadogClient(
                    apiKey=settings.DATADOG_API_KEY,
                    appKey=settings.DATADOG_APP_KEY,
                    periodicChecks=[
                        # TODO: compatibility with asyncio
                        # datadogClient.periodicCheck(
                        #     "online_users",
                        #     lambda: len(await osuToken.get_token_ids()),
                        # ),
                        # datadogClient.periodicCheck(
                        #     "multiplayer_matches",
                        #     lambda: len(await match.get_match_ids()),
                        # ),
                        # datadogClient.periodicCheck(
                        #     "chat_channels",
                        #     lambda: len(await channelList.getChannelNames()),
                        # ),
                    ],
                )
        except:
            logging.exception("Error creating datadog client")
            raise

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

        # We only wish to run the service's background jobs and redis pubsubs
        # on a single instance of bancho-service. Ideally, these should likely
        # be split into processes of their own (multiple app components within
        # the service), but for now we'll just run them all in the same process.
        # TODO:FIXME there is additionally an assumption made here that all
        # bancho-service instances will be run as processes on the same machine.
        raw_result = await glob.redis.get("bancho:primary_instance_pid")
        if raw_result is None or not psutil.pid_exists(int(raw_result)):
            logging.info("Starting background loops")
            await glob.redis.set("bancho:primary_instance_pid", os.getpid())

            logging.info("Starting user timeout loop")
            await tokenList.usersTimeoutCheckLoop()
            logging.info("Started user timeout loop")
            logging.info("Starting spam protection loop")
            await tokenList.spamProtectionResetLoop()
            logging.info("Started spam protection loop")

            # Connect to pubsub channels
            PUBSUB_HANDLERS = {
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
                "Starting pubsub listeners",
                extra={"handlers": list(PUBSUB_HANDLERS)},
            )
            pubsub_listener = pubSub.listener(
                redis_connection=glob.redis,
                handlers=PUBSUB_HANDLERS,
            )
            asyncio.create_task(pubsub_listener.run())
            logging.info(
                "Started pubsub listeners",
                extra={"handlers": list(PUBSUB_HANDLERS)},
            )

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

            # Allow grace period for ongoing connections to finish
            await asyncio.wait_for(
                http_server.close_all_connections(),
                timeout=settings.SHUTDOWN_HTTP_CONNECTION_TIMEOUT,
            )

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
