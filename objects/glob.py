"""Global objects and variables"""
from __future__ import annotations

import time
from typing import TYPE_CHECKING

from common.ddog import datadogClient
from common.files import fileBuffer, fileLocks
from common.web import schiavo
from objects import channelList, matchList, streamList, tokenList

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
channels = channelList.channelList()
matches = matchList.matchList()
fLocks = fileLocks.fileLocks()
fileBuffers = fileBuffer.buffersList()
schiavo = schiavo.schiavo()
dog = datadogClient.datadogClient()
verifiedCache = {}
pool = None
ircServer = None
busyThreads = 0

debug = False
outputRequestTime = False
outputPackets = False
gzip = False
localize = False
sentry = False
irc = False
restarting = False

startTime = int(time.time())
latestBuild = 0

streams = streamList.streamList()

groupPrivileges: dict[str, int] = {}
bcrypt_cache: dict[bytes, bytes] = {}
