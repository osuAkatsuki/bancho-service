from __future__ import annotations

import redis.asyncio as redis

import settings
from common.log import logger
from common.tracing_utils import tracef
from objects import banchoConfig
from objects import glob
from objects.dbPool import DBPool


async def startup() -> None:
    logger.info(
        "Starting up all services for selected component",
        extra={"component": settings.APP_COMPONENT},
    )

    # Connect to db
    logger.info("Connecting to SQL")
    try:
        glob.db = DBPool()
        await glob.db.start()
    except:
        logger.exception("Error connecting to sql")
        raise

    # Connect to redis
    logger.info("Connecting to redis")
    try:
        glob.redis = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            password=settings.REDIS_PASS,
            username=settings.REDIS_USER,
            ssl=settings.REDIS_USE_SSL,
        )

        glob.redis.smembers = tracef(glob.redis.smembers)  # type: ignore[method-assign]

        await glob.redis.ping()
    except:
        logger.exception("Error connecting to redis")
        raise

    # Load bancho_settings
    logger.info("Loading bancho settings")
    try:
        glob.banchoConf = banchoConfig.banchoConfig()
        await glob.banchoConf.loadSettings()
    except:
        logger.exception("Error loading bancho settings")
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

    if not settings.LOCALIZE_ENABLE:
        logger.info("User localization is disabled")

    if not settings.APP_GZIP:
        logger.info("Gzip compression is disabled")

    if settings.DEBUG:
        logger.info("Server running in debug mode")


async def shutdown() -> None:
    logger.info(
        "Shutting down all services for selected component",
        extra={"component": settings.APP_COMPONENT},
    )

    logger.info("Closing connection to redis")
    await glob.redis.close()
    logger.info("Closed connection to redis")

    logger.info("Closing connection(s) to MySQL")
    await glob.db.stop()
    logger.info("Closed connection(s) to MySQL")
