#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import logging
import os
import sys

sys.path.insert(1, os.path.join(sys.path[0], "../.."))

import lifecycle
from objects import osuToken
from objects.redisLock import redisLock

# TODO: this should be used in other places in the code
# and potentially abstracted into a more appropriate place
CHAT_SPAM_SAMPLE_INTERVAL = 10  # seconds


async def main() -> int:
    """bancho-service silences users by tracking how"""
    logging.info("Starting spam protection loop")
    try:
        await lifecycle.startup()
        while True:
            for token_id in await osuToken.get_token_ids():
                async with redisLock(
                    f"{osuToken.make_key(token_id)}:processing_lock",
                ):
                    await osuToken.update_token(token_id, spam_rate=0)

            await asyncio.sleep(CHAT_SPAM_SAMPLE_INTERVAL)
    finally:
        await lifecycle.shutdown()

    return 0


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
    except KeyboardInterrupt:
        exit_code = 0

    exit(exit_code)
