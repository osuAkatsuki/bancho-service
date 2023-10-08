#!/usr/bin/env bash
set -eo pipefail

PYPI_INDEX_URL="http://localhost:3141/cmyui/dev"

pip install -i $PYPI_INDEX_URL akatsuki-cli
akatsuki vault get bancho-service ${APP_ENV} -o .env

set -a
source .env
set +a

rm .env
