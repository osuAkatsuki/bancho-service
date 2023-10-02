"""Global objects and variables"""
from __future__ import annotations

import time
from typing import Optional
from typing import TYPE_CHECKING

from amplitude import Amplitude
from amplitude import Config as AmplitudeConfig

import settings

if TYPE_CHECKING:
    from concurrent.futures import ThreadPoolExecutor

    from redis import Redis

    from objects.dbPool import DBPool
    from common.ddog.datadogClient import datadogClient
    from irc.ircserver import Server as IRCServer
    from objects.banchoConfig import banchoConfig


DATADOG_PREFIX = "peppy"
BOT_NAME = "Aika"
application = None
db: DBPool
redis: Redis
banchoConf: banchoConfig
dog: Optional[datadogClient] = None
pool: ThreadPoolExecutor
ircServer: IRCServer

restarting = False

startTime = int(time.time())
latestBuild = 0

groupPrivileges: dict[str, int] = {}
bcrypt_cache: dict[bytes, bytes] = {}

amplitude = Amplitude(
    settings.AMPLITUDE_API_KEY,
    # our user ids start from 1000
    AmplitudeConfig(min_id_length=4),
)
