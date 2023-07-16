"""Global objects and variables"""
from __future__ import annotations

import time
from typing import TYPE_CHECKING

from amplitude import Amplitude
from common.ddog import datadogClient

import settings

if TYPE_CHECKING:
    from redis import Redis
    from common.db import dbConnector
    from objects.banchoConfig import banchoConfig
    from irc.ircserver import Server as IRCServer

DATADOG_PREFIX = "peppy"
BOT_NAME = "Aika"
application = None
db: dbConnector.db
redis: Redis
banchoConf: banchoConfig
dog = datadogClient.datadogClient()
pool = None
ircServer: IRCServer

restarting = False

startTime = int(time.time())
latestBuild = 0


groupPrivileges: dict[str, int] = {}
bcrypt_cache: dict[bytes, bytes] = {}


amplitude = Amplitude(settings.AMPLITUDE_API_KEY)
