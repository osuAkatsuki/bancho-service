from __future__ import annotations

import logging

from common.web.requestsManager import AsyncRequestHandler
from objects import glob


class handler(AsyncRequestHandler):
    async def get(self) -> None:
        try:
            await glob.redis.ping()
            await glob.db.fetch("SELECT 1")
        except Exception as exc:
            logging.warning("Failed health check", exc_info=exc)
            self.set_status(500)
        else:
            self.set_status(200)
