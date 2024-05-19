"""Global objects and variables"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING
from typing import Any

import httpx
from amplitude import Amplitude
from amplitude import Config as AmplitudeConfig

import settings

if TYPE_CHECKING:
    import tornado.web
    from redis.asyncio import Redis

    from objects.banchoConfig import banchoConfig
    from objects.dbPool import DBPool


http_client = httpx.AsyncClient()
application: tornado.web.Application | None = None
db: DBPool
redis: Redis[Any]
banchoConf: banchoConfig

restarting = False

startTime = int(time.time())
latestBuild = 0

groupPrivileges: dict[str, int] = {}
bcrypt_cache: dict[bytes, bytes] = {}

amplitude: Amplitude | None = None
if settings.AMPLITUDE_API_KEY:
    amplitude = Amplitude(
        settings.AMPLITUDE_API_KEY,
        # our user ids start from 1000
        AmplitudeConfig(min_id_length=4),
    )
