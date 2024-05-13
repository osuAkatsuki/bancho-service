from __future__ import annotations

from json import dumps
from typing import Any

from common.web.requestsManager import AsyncRequestHandler
from objects import glob


class handler(AsyncRequestHandler):
    async def get(self) -> None:
        statusCode = 400
        data: dict[str, Any] = {"message": "unknown error"}
        try:
            # Get online users count
            raw_online_users = await glob.redis.get("ripple:online_users")
            assert raw_online_users is not None

            data["result"] = int(raw_online_users.decode("utf-8"))

            # Status code and message
            statusCode = 200
            data["message"] = "ok"
        finally:
            # Add status code to data
            data["status"] = statusCode

            # Send response
            self.write(dumps(data))
            self.set_status(statusCode)
