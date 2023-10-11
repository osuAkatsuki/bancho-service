#!/usr/bin/env bash
set -eo pipefail

exec python3 workers/daemons/consume_pubsub_events.py
