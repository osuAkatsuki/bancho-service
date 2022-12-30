"""Global objects and variables"""
from __future__ import annotations

import time
from typing import TYPE_CHECKING

from common.ddog import datadogClient
from objects import matchList
from objects import tokenList

if TYPE_CHECKING:
    from redis import Redis
    from common.db import dbConnector
    from objects.banchoConfig import banchoConfig

DATADOG_PREFIX = "peppy"
BOT_NAME = "Aika"
application = None
db: dbConnector.db
redis: Redis
banchoConf: banchoConfig
tokens = tokenList.TokenList()
matches = matchList.MatchList()
dog = datadogClient.datadogClient()
pool = None
ircServer = None

restarting = False

startTime = int(time.time())
latestBuild = 0

groupPrivileges: dict[str, int] = {}
bcrypt_cache: dict[bytes, bytes] = {}
