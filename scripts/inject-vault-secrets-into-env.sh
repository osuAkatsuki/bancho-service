#!/usr/bin/env bash
set -eo pipefail

pip install akatsuki-cli
akatsuki vault get bancho-service ${APP_ENV} -o .env

set -a
source .env
set +a

rm .env
