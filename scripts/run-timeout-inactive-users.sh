#!/usr/bin/env bash
set -eo pipefail

exec python3 workers/crons/timeout_inactive_users.py
