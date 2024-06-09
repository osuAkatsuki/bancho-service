#!/usr/bin/env bash
set -eo pipefail

exec python3 workers/crons/trim_outdated_stream_messages.py
