#!/usr/bin/env python3.9
from __future__ import annotations

import os
import threading
from multiprocessing.pool import ThreadPool

import psutil
import redis
import tornado.gen
import tornado.httpserver
import tornado.ioloop
import tornado.web

import settings
from common.db import dbConnector
from common.ddog import datadogClient
from common.log import logger
from common.redis import pubSub
from handlers import apiFokabotMessageHandler
from handlers import apiIsOnlineHandler
from handlers import apiOnlineUsersHandler
from handlers import apiServerStatusHandler
from handlers import apiVerifiedStatusHandler
from handlers import ciTriggerHandler
from handlers import mainHandler
from helpers import consoleHelper
from helpers import systemHelper as system
from irc import ircserver
from objects import banchoConfig
from objects import channelList
from objects import fokabot
from objects import glob
from objects import match
from objects import osuToken
from objects import streamList
from objects import tokenList
from pubSubHandlers import banHandler
from pubSubHandlers import changeUsernameHandler
from pubSubHandlers import disconnectHandler
from pubSubHandlers import notificationHandler
from pubSubHandlers import unbanHandler
from pubSubHandlers import updateSilenceHandler
from pubSubHandlers import updateStatsHandler
from pubSubHandlers import wipeHandler


def make_app():
    return tornado.web.Application(
        [
            (r"/", mainHandler.handler),
            (r"/api/v1/isOnline", apiIsOnlineHandler.handler),
            (r"/api/v1/onlineUsers", apiOnlineUsersHandler.handler),
            (r"/api/v1/serverStatus", apiServerStatusHandler.handler),
            (r"/api/v1/ciTrigger", ciTriggerHandler.handler),
            (r"/api/v1/verifiedStatus", apiVerifiedStatusHandler.handler),
            (r"/api/v1/fokabotMessage", apiFokabotMessageHandler.handler),
        ],
    )


if __name__ == "__main__":
    try:
        # TODO: do we need this anymore now with stateless design?
        # (not using filesystem anymore for things like .data/)
        os.chdir(os.path.dirname(os.path.realpath(__file__)))

        logger.configure_logging()

        # Connect to db
        try:
            logger.info("Connecting to sql database")
            glob.db = dbConnector.db(
                host=settings.DB_HOST,
                username=settings.DB_USER,
                password=settings.DB_PASS,
                database=settings.DB_NAME,
                initialSize=settings.DB_WORKERS,
            )
        except Exception as exc:
            logger.error(
                "Failed to connect to sql database",
                exc_info=exc,
                extra={
                    "host": settings.DB_HOST,
                    "username": settings.DB_USER,
                    "database": settings.DB_NAME,
                },
            )
            raise

        # Connect to redis
        try:
            logger.info("Connecting to redis")
            glob.redis = redis.Redis(
                settings.REDIS_HOST,
                settings.REDIS_PORT,
                settings.REDIS_DB,
                settings.REDIS_PASS,
            )
            glob.redis.ping()
        except Exception as exc:
            logger.error(
                "Failed to connect to redis",
                exc_info=exc,
                extra={
                    "host": settings.REDIS_HOST,
                    "port": settings.REDIS_PORT,
                    "db": settings.REDIS_DB,
                },
            )
            raise

        # Load bancho_settings
        try:
            logger.info("Loading bancho settings")
            glob.banchoConf = banchoConfig.banchoConfig()
        except Exception as exc:
            logger.error("Error loading bancho settings", exc_info=exc)
            raise

        # Create threads pool
        try:
            logger.info(
                "Creating threads pool",
                extra={"num_threads": settings.APP_THREADS},
            )
            glob.pool = ThreadPool(processes=settings.APP_THREADS)
        except Exception as exc:
            logger.error(
                "Error creating threads pool",
                exc_info=exc,
                extra={"threads": settings.APP_THREADS},
            )
            raise

        # fetch privilege groups into memory
        # TODO: this is an optimization because ripple previously
        # fetched this so frequently. this is not robust as privilege
        # groups may change during runtime.
        try:
            logger.info("Caching privilege groups to memory")
            glob.groupPrivileges = {
                row["name"].lower(): row["privileges"]
                for row in (
                    glob.db.fetchAll(
                        "SELECT name, privileges FROM privileges_groups",
                    )
                    or []
                )
            }
        except Exception as exc:
            logger.error("Error caching privilege groups to memory", exc_info=exc)
            raise

        try:
            logger.info("Connecting the in-game bot - Aika")
            fokabot.connect()
        except Exception as exc:
            logger.error("Error connecting the in-game bot - Aika", exc_info=exc)
            raise

        try:
            logger.info("Loading channels into redis")
            channelList.loadChannels()
        except Exception as exc:
            logger.error("Error loading channels into redis", exc_info=exc)
            raise

        try:
            logger.info("Loading streams into redis")
            streamList.add("main")
            streamList.add("lobby")
        except Exception as exc:
            logger.error("Error loading streams into redis", exc_info=exc)
            raise

        if not settings.LOCALIZE_ENABLE:
            logger.warning("User localization is disabled")

        if not settings.APP_GZIP:
            logger.warning("Gzip compression is disabled")

        if settings.DEBUG:
            logger.warning("Running in debug mode")

        glob.application = make_app()

        # set up datadog
        try:
            logger.info("Initializing datadog client")
            if settings.DATADOG_ENABLE:
                glob.dog = datadogClient.datadogClient(
                    apiKey=settings.DATADOG_API_KEY,
                    appKey=settings.DATADOG_APP_KEY,
                    periodicChecks=[
                        datadogClient.periodicCheck(
                            "online_users",
                            lambda: len(osuToken.get_token_ids()),
                        ),
                        datadogClient.periodicCheck(
                            "multiplayer_matches",
                            lambda: len(match.get_match_ids()),
                        ),
                        datadogClient.periodicCheck(
                            "chat_channels",
                            lambda: len(channelList.getChannelNames()),
                        ),
                    ],
                )
        except Exception as exc:
            logger.error(
                "Error initializing datadog client",
                exc_info=exc,
            )
            raise

        # start irc server if configured
        if settings.IRC_ENABLE:
            try:
                logger.info(
                    "Starting IRC server in a background thread",
                    extra={"port": settings.IRC_PORT},
                )
                threading.Thread(
                    target=lambda: ircserver.main(port=settings.IRC_PORT),
                ).start()
            except Exception as exc:
                logger.error(
                    "Error starting IRC server",
                    exc_info=exc,
                    extra={"port": settings.IRC_PORT},
                )
                raise

        # We only wish to run the service's background jobs and redis pubsubs
        # on a single instance of bancho-service. Ideally, these should likely
        # be split into processes of their own (multiple app components within
        # the service), but for now we'll just run them all in the same process.
        # TODO:FIXME there is additionally an assumption made here that all
        # bancho-service instances will be run as processes on the same machine.
        try:
            raw_result = glob.redis.get("bancho:primary_instance_pid")
            if raw_result is None or not psutil.pid_exists(int(raw_result)):
                logger.info("Starting background loops")
                glob.redis.set("bancho:primary_instance_pid", os.getpid())

                tokenList.usersTimeoutCheckLoop()
                tokenList.spamProtectionResetLoop()

                # Connect to pubsub channels
                pubSub.listener(
                    glob.redis,
                    {
                        "peppy:ban": banHandler.handler(),
                        "peppy:unban": unbanHandler.handler(),
                        "peppy:silence": updateSilenceHandler.handler(),
                        "peppy:disconnect": disconnectHandler.handler(),
                        "peppy:notification": notificationHandler.handler(),
                        "peppy:change_username": changeUsernameHandler.handler(),
                        "peppy:update_cached_stats": updateStatsHandler.handler(),
                        "peppy:wipe": wipeHandler.handler(),
                        "peppy:reload_settings": lambda x: x == b"reload"
                        and glob.banchoConf.reload(),
                    },
                ).start()
        except Exception as exc:
            logger.error(
                "Error starting background loops",
                exc_info=exc,
            )
            raise

        # Start tornado
        glob.application.listen(settings.APP_PORT)

        logger.info(
            "Server listening for HTTP clients",
            extra={"port": settings.APP_PORT},
        )

        tornado.ioloop.IOLoop.instance().start()
    finally:
        system.dispose()
