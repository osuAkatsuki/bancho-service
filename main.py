#!/usr/bin/env python3.9
from __future__ import annotations

import ddtrace

ddtrace.patch_all()

import os
import asyncio
import threading
from datetime import datetime as dt

import redis

from cmyui.logging import Ansi, log
from common.db import dbConnector
from common.ddog import datadogClient
from common.redis import pubSub
from handlers import (
    apiFokabotMessageHandler,
    apiIsOnlineHandler,
    apiOnlineUsersHandler,
    apiServerStatusHandler,
    mainHandler,
)
from helpers import systemHelper as system
from irc import ircserver
from objects import banchoConfig, fokabot, glob
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
from fastapi import FastAPI

# TODO: check if this is still needed
os.chdir(os.path.dirname(os.path.realpath(__file__)))


def make_app():
    app = FastAPI()
    app.include_router(mainHandler.router)
    app.include_router(apiIsOnlineHandler.router)
    app.include_router(apiOnlineUsersHandler.router)
    app.include_router(apiServerStatusHandler.router)
    app.include_router(apiFokabotMessageHandler.router)

    @app.on_event("startup")
    async def on_startup():
        # set up sql db
        glob.db = dbConnector.db(
            host=settings.DB_HOST,
            username=settings.DB_USER,
            password=settings.DB_PASS,
            database=settings.DB_NAME,
            initialSize=settings.DB_WORKERS,
        )

        # set up redis
        glob.redis = redis.Redis(
            settings.REDIS_HOST,
            settings.REDIS_PORT,
            settings.REDIS_DB,
            settings.REDIS_PASS,
        )
        glob.redis.ping()
        glob.redis.set("ripple:online_users", 0)
        glob.redis.delete(*glob.redis.keys("peppy:*"))
        glob.redis.delete(*glob.redis.keys("akatsuki:sessions:*"))
        glob.redis.set("peppy:version", glob.VERSION)

        # Load bancho_settings
        try:
            glob.banchoConf = banchoConfig.banchoConfig()
        except:
            log(f"Error loading bancho settings.", Ansi.LMAGENTA)
            raise

        # Delete old bancho sessions
        glob.tokens.deleteBanchoSessions()

        asyncio.create_task(glob.tokens.usersTimeoutCheckLoop())
        asyncio.create_task(glob.tokens.spamProtectionResetLoop())
        asyncio.create_task(glob.matches.cleanupLoop())

        log(f"Connecting {glob.BOT_NAME}", Ansi.LMAGENTA)
        fokabot.connect()

        glob.channels.loadChannels()

        # Initialize stremas
        glob.streams.add("main")
        glob.streams.add("lobby")

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
                        lambda: len(glob.matches.matches),
                    ),
                    # datadogClient.periodicCheck("ram_clients", lambda: generalUtils.getTotalSize(glob.tokens)),
                    # datadogClient.periodicCheck("ram_matches", lambda: generalUtils.getTotalSize(glob.matches)),
                    # datadogClient.periodicCheck("ram_channels", lambda: generalUtils.getTotalSize(glob.channels)),
                    # datadogClient.periodicCheck("ram_file_buffers", lambda: generalUtils.getTotalSize(glob.fileBuffers)),
                    # datadogClient.periodicCheck("ram_file_locks", lambda: generalUtils.getTotalSize(glob.fLocks)),
                    # datadogClient.periodicCheck("ram_datadog", lambda: generalUtils.getTotalSize(glob.datadogClient)),
                    # datadogClient.periodicCheck("ram_verified_cache", lambda: generalUtils.getTotalSize(glob.verifiedCache)),
                    # datadogClient.periodicCheck("ram_irc", lambda: generalUtils.getTotalSize(glob.ircServer)),
                    # datadogClient.periodicCheck("ram_tornado", lambda: generalUtils.getTotalSize(glob.application)),
                    # datadogClient.periodicCheck("ram_db", lambda: generalUtils.getTotalSize(glob.db)),
                ],
            )

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

    @app.on_event("shutdown")
    async def on_shutdown():
        glob.redis.close()
        system.dispose()

    return app


def main() -> int:
    log("Ensuring folders.", Ansi.LMAGENTA)
    if not os.path.exists(".data"):
        os.makedirs(".data", 0o770)

    # Get build date for login notifications
    with open("build.date") as f:
        timestamp = dt.utcfromtimestamp(int(f.read()))
        glob.latestBuild = timestamp.strftime("%b %d %Y")

    return 0


app = make_app()

if __name__ == "__main__":
    raise SystemExit(main())
