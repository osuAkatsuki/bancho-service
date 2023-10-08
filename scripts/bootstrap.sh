#!/usr/bin/env bash
set -eo pipefail

cd /srv/root

if [[ -z "$PULL_SECRETS_FROM_VAULT" ]]; then
  pip install -i $PYPI_INDEX_URL akatsuki-cli
  akatsuki vault get bancho-service production -o .env
  source .env
fi

# await database availability
/scripts/await-service.sh $DB_HOST $DB_PORT $SERVICE_READINESS_TIMEOUT

# await redis availability
/scripts/await-service.sh $REDIS_HOST $REDIS_PORT $SERVICE_READINESS_TIMEOUT

# run the service
exec /scripts/run-service.sh
