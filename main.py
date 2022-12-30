#!/usr/bin/env python3.9
from __future__ import annotations

# import ddtrace

# ddtrace.patch_all()

import os
import threading
from datetime import datetime as dt
from multiprocessing.pool import ThreadPool

import redis
import tornado.gen
import tornado.httpserver
import tornado.ioloop
import tornado.web

from cmyui.logging import Ansi, log, printc
from common.constants import bcolors
from common.db import dbConnector
from common.ddog import datadogClient
from common.redis import pubSub
from handlers import (
    apiFokabotMessageHandler,
    apiIsOnlineHandler,
    apiOnlineUsersHandler,
    apiServerStatusHandler,
    apiVerifiedStatusHandler,
    ciTriggerHandler,
    mainHandler,
)
from helpers import consoleHelper
from helpers import systemHelper as system
from irc import ircserver
from objects import banchoConfig, fokabot, glob, streamList, channelList, match
from pubSubHandlers import (
    banHandler,
    changeUsernameHandler,
    disconnectHandler,
    notificationHandler,
    unbanHandler,
    updateSilenceHandler,
    updateStatsHandler,
    wipeHandler,
)
import settings


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
        "   _/    _/  _/  _/      _/_/_/  _/_/_/_/    _/_/_/  _/    _/  _/  _/",
        "  _/_/_/_/  _/_/      _/    _/    _/      _/_/      _/    _/  _/_/      _/",
        " _/    _/  _/  _/    _/    _/    _/          _/_/  _/    _/  _/  _/    _/",
        "_/    _/  _/    _/    _/_/_/      _/_/  _/_/_/      _/_/_/  _/    _/  _/",
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

        # log("Ensuring folders.", Ansi.LMAGENTA)
        # if not os.path.exists(".data"):
        #     os.makedirs(".data", 0o770)

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

        # Empty redis cache
        # try:
        #     glob.redis.set("ripple:online_users", 0)
        #     glob.redis.delete(*glob.redis.keys("peppy:*"))
        #     glob.redis.delete(*glob.redis.keys("akatsuki:sessions:*"))
        # except redis.exceptions.ResponseError:
        #     # Script returns error if there are no keys starting with peppy:*
        #     pass

        # Load bancho_settings
        try:
            glob.banchoConf = banchoConfig.banchoConfig()
        except:
            log(f"Error loading bancho settings.", Ansi.LMAGENTA)
            raise

        # Delete old bancho sessions
        glob.tokens.deleteBanchoSessions()

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

        log(f"Connecting {glob.BOT_NAME}", Ansi.LMAGENTA)
        fokabot.connect()

        channelList.loadChannels()

        # Initialize stremas
        streamList.add("main")
        streamList.add("lobby")

        log("Starting background loops.", Ansi.LMAGENTA)

        glob.tokens.usersTimeoutCheckLoop()
        glob.tokens.spamProtectionResetLoop()
        # glob.matches.cleanupLoop()

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
                            lambda: len(glob.tokens.tokens),
                        ),
                        datadogClient.periodicCheck(
                            "multiplayer_matches",
                            lambda: len(match.get_match_ids()),
                        ),
                        # datadogClient.periodicCheck("ram_clients", lambda: generalUtils.getTotalSize(glob.tokens)),
                        # datadogClient.periodicCheck("ram_matches", lambda: generalUtils.getTotalSize(glob.matches)),
                        # datadogClient.periodicCheck("ram_channels", lambda: generalUtils.getTotalSize(glob.channels)),
                        # datadogClient.periodicCheck("ram_datadog", lambda: generalUtils.getTotalSize(glob.datadogClient)),
                        # datadogClient.periodicCheck("ram_verified_cache", lambda: generalUtils.getTotalSize(glob.verifiedCache)),
                        # datadogClient.periodicCheck("ram_irc", lambda: generalUtils.getTotalSize(glob.ircServer)),
                        # datadogClient.periodicCheck("ram_tornado", lambda: generalUtils.getTotalSize(glob.application)),
                        # datadogClient.periodicCheck("ram_db", lambda: generalUtils.getTotalSize(glob.db)),
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

        # fetch priv groups (optimization by cmyui)
        glob.groupPrivileges = {
            row["name"].lower(): row["privileges"]
            for row in glob.db.fetchAll(
                "SELECT name, privileges " "FROM privileges_groups",
            )
        }

        # Server start message and console output
        log(
            f"Tornado listening for HTTP(s) clients on 127.0.0.1:{settings.APP_PORT}.",
            Ansi.LMAGENTA,
        )

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

        # Start tornado
        glob.application.listen(settings.APP_PORT)
        tornado.ioloop.IOLoop.instance().start()
    finally:
        system.dispose()
