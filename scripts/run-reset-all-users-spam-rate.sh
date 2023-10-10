#!/usr/bin/env bash
set -eo pipefail

exec python3 workers/crons/reset_all_users_spam_rate.py
