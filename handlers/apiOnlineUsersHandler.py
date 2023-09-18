from __future__ import annotations

from json import dumps
from typing import Union

from common.web.requestsManager import AsyncRequestHandler
from objects import glob


class handler(AsyncRequestHandler):
    async def get(self) -> None:
        statusCode = 400
        data: dict[str, Union[int, str]] = {"message": "unknown error"}
        try:
            # Get online users count
            data["result"] = int(await glob.redis.get("ripple:online_users").decode("utf-8"))

            # Status code and message
            statusCode = 200
            data["message"] = "ok"
        finally:
            # Add status code to data
            data["status"] = statusCode

            # Send response
            self.write(dumps(data))
            self.set_status(statusCode)
