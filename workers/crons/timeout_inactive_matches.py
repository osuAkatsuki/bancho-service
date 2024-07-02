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
from objects import match
from objects import matchList
from objects import slot
from objects.redisLock import redisLock

FIVE_MINUTES = 60 * 5


async def _delete_match_if_inactive(multiplayer_match: match.Match) -> bool:
    slots = await slot.get_slots(multiplayer_match["match_id"])
    if not any([slot["user_id"] for slot in slots]):
        logging.warning(
            "Timing out empty match",
            extra={"match_id": multiplayer_match["match_id"]},
        )
        await matchList.disposeMatch(multiplayer_match["match_id"])
        return True

    return False


async def _timeout_inactive_matches() -> None:
    logging.info("Timing out inactive matches")
    matches_deleted = 0
    for match_id in await match.get_match_ids():
        multiplayer_match = None
        try:
            async with redisLock(f"{match.make_key(match_id)}:lock"):
                multiplayer_match = await match.get_match(match_id)
                if multiplayer_match is None:
                    continue

                revoked = await _delete_match_if_inactive(multiplayer_match)
                matches_deleted += revoked

        except Exception:
            logging.exception(
                "An error occurred while disconnecting a timed out match",
                extra={"match_id": match_id},
            )

    logging.info(
        "Finished timing out inactive matches",
        extra={"tokens_revoked": matches_deleted},
    )


async def main() -> int:
    logging.info("Starting inactive token timeout loop")
    try:
        await lifecycle.startup()
        while True:
            await _timeout_inactive_matches()
            await asyncio.sleep(FIVE_MINUTES)
    finally:
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
