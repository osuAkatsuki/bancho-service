#!/usr/bin/env python3

from __future__ import annotations

import asyncio
import atexit
import logging
import os
import sys

sys.path.insert(1, os.path.join(sys.path[0], "../.."))

import lifecycle
from common import exception_handling
from common.log import logging_config
from common.ripple import user_utils
from objects import glob


async def main() -> int:
    await lifecycle.startup()
    users = await glob.db.fetchAll("SELECT id FROM users WHERE privileges & 3 = 3")
    for user in users:
        await user_utils.recalculate_and_update_first_place_scores(user["id"])
        logging.info("Recalculated first place scores for user %d", user["id"])
    await lifecycle.shutdown()
    return 0


if __name__ == "__main__":
    logging_config.configure_logging()
    exception_handling.hook_exception_handlers()
    atexit.register(exception_handling.unhook_exception_handlers)
    try:
        exit_code = asyncio.run(main())
    except KeyboardInterrupt:
        exit_code = 0
    exit(exit_code)
