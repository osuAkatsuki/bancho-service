#!/usr/bin/env bash
set -eo pipefail

cd /srv/root

if [[ -z "$PULL_SECRETS_FROM_VAULT" ]]; then
  /scripts/inject-vault-secrets-into-env.sh
fi

# await database availability
/scripts/await-service.sh $DB_HOST $DB_PORT $SERVICE_READINESS_TIMEOUT

# await redis availability
/scripts/await-service.sh $REDIS_HOST $REDIS_PORT $SERVICE_READINESS_TIMEOUT

# run the service
exec /scripts/run-service.sh
