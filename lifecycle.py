from __future__ import annotations

import asyncio
import logging.config

import redis.asyncio as redis

import settings
from irc import ircserver
from objects import banchoConfig
from objects import channelList
from objects import fokabot
from objects import glob
from objects import streamList
from objects.dbPool import DBPool


async def startup() -> None:
    logging.info(
        "Starting up all services for selected component",
        extra={"component": settings.APP_COMPONENT},
    )

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


async def shutdown() -> None:
    logging.info(
        "Shutting down all services for selected component",
        extra={"component": settings.APP_COMPONENT},
    )

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
