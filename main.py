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
from cmyui.logging import Ansi
from cmyui.logging import log
from cmyui.logging import printc

import settings
from common.constants import bcolors
from common.db import dbConnector
from common.ddog import datadogClient
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


ASCII_LOGO = "\n".join(
    [
        "      _/_/    _/                    _/                          _/        _/",
        "   _/    _/  _/  _/      _/_/_/  _/_/_/_/    _/_/_/  _/    _/  _/  _/       ",
        "  _/_/_/_/  _/_/      _/    _/    _/      _/_/      _/    _/  _/_/      _/  ",
        " _/    _/  _/  _/    _/    _/    _/          _/_/  _/    _/  _/  _/    _/   ",
        "_/    _/  _/    _/    _/_/_/      _/_/  _/_/_/      _/_/_/  _/    _/  _/    ",
    ],
)

if __name__ == "__main__":
    try:
        # Server start
        printc(ASCII_LOGO, Ansi.LGREEN)
        log(f"Welcome to Akatsuki's bancho-service", Ansi.LGREEN)
        log("Made by the Ripple and Akatsuki teams", Ansi.LGREEN)
        log(
            f"{bcolors.UNDERLINE}https://github.com/osuAkatsuki/bancho-service",
            Ansi.LGREEN,
        )
        log("Press CTRL+C to exit\n", Ansi.LGREEN)

        # TODO: do we need this anymore now with stateless design?
        # (not using filesystem anymore for things like .data/)
        os.chdir(os.path.dirname(os.path.realpath(__file__)))

        # Connect to db
        try:
            log("Connecting to SQL.", Ansi.LMAGENTA)
            glob.db = dbConnector.db(
                host=settings.DB_HOST,
                username=settings.DB_USER,
                password=settings.DB_PASS,
                database=settings.DB_NAME,
                initialSize=settings.DB_WORKERS,
            )
        except:
            log(f"Error connecting to sql.", Ansi.LRED)
            raise

        # Connect to redis
        try:
            log("Connecting to redis.", Ansi.LMAGENTA)
            glob.redis = redis.Redis(
                settings.REDIS_HOST,
                settings.REDIS_PORT,
                settings.REDIS_DB,
                settings.REDIS_PASS,
            )
            glob.redis.ping()
        except:
            log(f"Error connecting to redis.", Ansi.LRED)
            raise

        # Load bancho_settings
        try:
            glob.banchoConf = banchoConfig.banchoConfig()
        except:
            log(f"Error loading bancho settings.", Ansi.LMAGENTA)
            raise

        # Create threads pool
        try:
            glob.pool = ThreadPool(processes=settings.APP_THREADS)
        except ValueError:
            log(f"Error creating threads pool.", Ansi.LRED)
            consoleHelper.printError()
            consoleHelper.printColored(
                "[!] Error while creating threads pool. Please check your config.ini and run the server again",
                bcolors.RED,
            )
            raise

        # fetch privilege groups into memory
        # TODO: this is an optimization because ripple previously
        # fetched this so frequently. this is not robust as privilege
        # groups may change during runtime.
        glob.groupPrivileges = {
            row["name"].lower(): row["privileges"]
            for row in (
                glob.db.fetchAll(
                    "SELECT name, privileges FROM privileges_groups",
                )
                or []
            )
        }

        channelList.loadChannels()

        # Initialize stremas
        streamList.add("main")
        streamList.add("lobby")

        log(f"Connecting {glob.BOT_NAME}", Ansi.LMAGENTA)
        fokabot.connect()

        if not settings.LOCALIZE_ENABLE:
            log("User localization is disabled.", Ansi.LYELLOW)

        if not settings.APP_GZIP:
            log("Gzip compression is disabled.", Ansi.LYELLOW)

        if settings.DEBUG:
            log("Server running in debug mode.", Ansi.LYELLOW)

        glob.application = make_app()

        # set up datadog
        try:
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
        except:
            log("Error creating datadog client.", Ansi.LRED)
            raise

        # start irc server if configured
        if settings.IRC_ENABLE:
            log(
                f"IRC server listening on 127.0.0.1:{settings.IRC_PORT}.",
                Ansi.LMAGENTA,
            )
            threading.Thread(
                target=lambda: ircserver.main(port=settings.IRC_PORT),
            ).start()

        # We only wish to run the service's background jobs and redis pubsubs
        # on a single instance of bancho-service. Ideally, these should likely
        # be split into processes of their own (multiple app components within
        # the service), but for now we'll just run them all in the same process.
        # TODO:FIXME there is additionally an assumption made here that all
        # bancho-service instances will be run as processes on the same machine.
        raw_result = glob.redis.get("bancho:primary_instance_pid")
        if raw_result is None or not psutil.pid_exists(int(raw_result)):
            log("Starting background loops.", Ansi.LMAGENTA)
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
                    "peppy:username_changed": changeUsernameHandler.handler(),
                    "peppy:update_cached_stats": updateStatsHandler.handler(),
                    "peppy:wipe": wipeHandler.handler(),
                    "peppy:reload_settings": lambda x: x == b"reload"
                    and glob.banchoConf.reload(),
                },
            ).start()

        # Start tornado
        glob.application.listen(settings.APP_PORT)

        log(
            f"Tornado listening for HTTP(s) clients on 127.0.0.1:{settings.APP_PORT}.",
            Ansi.LMAGENTA,
        )

        tornado.ioloop.IOLoop.instance().start()
    finally:
        system.dispose()
