#!/usr/bin/env bash
set -eo pipefail

exec python3 workers/daemons/trim_outdated_stream_messages.py
