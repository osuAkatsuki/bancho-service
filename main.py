#!/usr/bin/env python3.9
from __future__ import annotations

import asyncio
import os
import threading
from concurrent.futures import ThreadPoolExecutor

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
from objects.dbPool import DBPool
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

# XXX: temporary for debugging purposes
import sys
import signal
import traceback
from datetime import datetime


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

        # Connect to db
        try:
            log("Connecting to SQL.", Ansi.LMAGENTA)
            glob.db = DBPool()
            await glob.db.start()
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
            await glob.banchoConf.loadSettings()
        except:
            log(f"Error loading bancho settings.", Ansi.LMAGENTA)
            raise

        # Create threads pool
        try:
            glob.pool = ThreadPoolExecutor(max_workers=settings.APP_THREADS)
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
                await glob.db.fetchAll(
                    "SELECT name, privileges FROM privileges_groups",
                )
                or []
            )
        }

        await channelList.loadChannels()

        # Initialize stremas
        streamList.add("main")
        streamList.add("lobby")

        log(f"Connecting {glob.BOT_NAME}", Ansi.LMAGENTA)
        await fokabot.connect()

        if not settings.LOCALIZE_ENABLE:
            log("User localization is disabled.", Ansi.LYELLOW)

        if not settings.APP_GZIP:
            log("Gzip compression is disabled.", Ansi.LYELLOW)

        if settings.DEBUG:
            log("Server running in debug mode.", Ansi.LYELLOW)

        glob.application = make_app()

        # start irc server if configured
        if settings.IRC_ENABLE:
            log(
                f"IRC server listening on 127.0.0.1:{settings.IRC_PORT}.",
                Ansi.LMAGENTA,
            )
            glob.pool.submit(ircserver.main, port=settings.IRC_PORT)

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

            await tokenList.usersTimeoutCheckLoop()
            await tokenList.spamProtectionResetLoop()

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

        log(
            f"Tornado listening for HTTP(s) clients on 127.0.0.1:{settings.APP_PORT}.",
            Ansi.LMAGENTA,
        )
        shutdown_event = asyncio.Event()
        await shutdown_event.wait()
    finally:
        system.dispose()

    return 0


if __name__ == "__main__":
    exit(asyncio.run(main()))
