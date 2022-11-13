import os

from dotenv import load_dotenv

load_dotenv()

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

APP_PORT = int(os.environ["APP_PORT"])
APP_THREADS = int(os.environ["APP_THREADS"])
APP_GZIP = os.environ["APP_GZIP"] == "1"
APP_GZIP_LEVEL = int(os.environ["APP_GZIP_LEVEL"])
APP_CI_KEY = os.environ["APP_CI_KEY"]
APP_API_KEY = os.environ["APP_API_KEY"]

MIRROR_URL = os.environ["MIRROR_URL"]
MIRROR_API_KEY = os.environ["MIRROR_API_KEY"]

DEBUG = os.environ["DEBUG"] == "1"

SENTRY_ENABLE = os.environ["SENTRY_ENABLE"] == "1"
SENTRY_BANCHO_DSN = os.environ["SENTRY_BANCHO_DSN"]
SENTRY_IRC_DSN = os.environ["SENTRY_IRC_DSN"]

DISCORD_ENABLE = os.environ["DISCORD_ENABLE"] == "1"
DISCORD_BOT_URL = os.environ["DISCORD_BOT_URL"]
DISCORD_DEV_GROUP = os.environ["DISCORD_DEV_GROUP"]

DATADOG_ENABLE = os.environ["DATADOG_ENABLE"] == "1"
DATADOG_API_KEY = os.environ["DATADOG_API_KEY"]
DATADOG_APP_KEY = os.environ["DATADOG_APP_KEY"]

IRC_ENABLE = os.environ["IRC_ENABLE"] == "1"
IRC_PORT = int(os.environ["IRC_PORT"])
IRC_HOSTNAME = os.environ["IRC_HOSTNAME"]

LOCALIZE_ENABLE = os.environ["LOCALIZE_ENABLE"] == "1"
LOCALIZE_IP_API_URL = os.environ["LOCALIZE_IP_API_URL"]

WEBHOOK_NOW_RANKED = os.environ["WEBHOOK_NOW_RANKED"]
WEBHOOK_RANK_REQUESTS = os.environ["WEBHOOK_RANK_REQUESTS"]
WEBHOOK_AC_GENERAL = os.environ["WEBHOOK_AC_GENERAL"]
WEBHOOK_AC_CONFIDENTIAL = os.environ["WEBHOOK_AC_CONFIDENTIAL"]

