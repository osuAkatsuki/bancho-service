from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

load_dotenv()


def read_bool(val: str) -> bool:
    return val.lower() in ("true", "1")


APP_ENV = os.environ["APP_ENV"]
APP_COMPONENT = os.environ["APP_COMPONENT"]

DB_HOST = os.environ["DB_HOST"]
DB_PORT = int(os.environ["DB_PORT"])
DB_USER = os.environ["DB_USER"]
DB_PASS = os.environ["DB_PASS"]
DB_NAME = os.environ["DB_NAME"]
DB_WORKERS = int(os.environ["DB_WORKERS"])

REDIS_HOST = os.environ["REDIS_HOST"]
REDIS_PORT = int(os.environ["REDIS_PORT"])
REDIS_DB = int(os.environ["REDIS_DB"])
REDIS_PASS = os.environ["REDIS_PASS"]

# stupid temporary hack for load balancing
if "--port" in sys.argv:
    APP_PORT = int(sys.argv[sys.argv.index("--port") + 1])
else:
    APP_PORT = int(os.environ["APP_PORT"])

APP_GZIP = read_bool(os.environ["APP_GZIP"])
APP_GZIP_LEVEL = int(os.environ["APP_GZIP_LEVEL"])
APP_CI_KEY = os.environ["APP_CI_KEY"]
APP_API_KEY = os.environ["APP_API_KEY"]

SHUTDOWN_HTTP_CONNECTION_TIMEOUT = int(os.environ["SHUTDOWN_HTTP_CONNECTION_TIMEOUT"])

MIRROR_URL = os.environ["MIRROR_URL"]

DEBUG = os.environ["DEBUG"] == "1"

IRC_ENABLE = os.environ["IRC_ENABLE"] == "1"
IRC_PORT = int(os.environ["IRC_PORT"])
IRC_HOSTNAME = os.environ["IRC_HOSTNAME"]

LOCALIZE_ENABLE = os.environ["LOCALIZE_ENABLE"] == "1"
LOCALIZE_IP_API_URL = os.environ["LOCALIZE_IP_API_URL"]

WEBHOOK_NOW_RANKED = os.environ["WEBHOOK_NOW_RANKED"]
WEBHOOK_RANK_REQUESTS = os.environ["WEBHOOK_RANK_REQUESTS"]
WEBHOOK_AC_GENERAL = os.environ["WEBHOOK_AC_GENERAL"]
WEBHOOK_AC_CONFIDENTIAL = os.environ["WEBHOOK_AC_CONFIDENTIAL"]

AMPLITUDE_API_KEY = os.environ["AMPLITUDE_API_KEY"]
