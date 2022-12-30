"""Global objects and variables"""
from __future__ import annotations

import time
from typing import TYPE_CHECKING

from common.ddog import datadogClient
from common.web import schiavo
from objects import channelList
from objects import matchList
from objects import tokenList

if TYPE_CHECKING:
    from redis import Redis

    from common.db import dbConnector

try:
    with open("version") as f:
        VERSION = f.read().strip()
    if VERSION == "":
        raise Exception
except:
    VERSION = "Unknown"

DATADOG_PREFIX = "peppy"
BOT_NAME = "Aika"
application = None
db: dbConnector.db
redis: Redis
conf = None
banchoConf = None
tokens = tokenList.tokenList()
matches = matchList.matchList()
schiavo = schiavo.schiavo()
dog = datadogClient.datadogClient()
verifiedCache = {}
pool = None
ircServer = None

restarting = False

startTime = int(time.time())
latestBuild = 0

groupPrivileges: dict[str, int] = {}
bcrypt_cache: dict[bytes, bytes] = {}
