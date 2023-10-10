#!/usr/bin/env bash
set -eo pipefail

exec python3 workers/crons/reset_all_tokens_spam_rate.py
