"""Global objects and variables"""
from __future__ import annotations

import time
from typing import Optional
from typing import TYPE_CHECKING

import httpx
from amplitude import Amplitude
from amplitude import Config as AmplitudeConfig

import settings

if TYPE_CHECKING:
    from redis.asyncio import Redis

    from objects.dbPool import DBPool
    from irc.ircserver import Server as IRCServer
    from objects.banchoConfig import banchoConfig


BOT_NAME = "Aika"
http_client = httpx.AsyncClient()
application = None
db: DBPool
redis: Redis
banchoConf: banchoConfig
ircServer: IRCServer

restarting = False

startTime = int(time.time())
latestBuild = 0

groupPrivileges: dict[str, int] = {}
bcrypt_cache: dict[bytes, bytes] = {}

amplitude: Optional[Amplitude] = None
if settings.AMPLITUDE_API_KEY:
    amplitude = Amplitude(
        settings.AMPLITUDE_API_KEY,
        # our user ids start from 1000
        AmplitudeConfig(min_id_length=4),
    )
