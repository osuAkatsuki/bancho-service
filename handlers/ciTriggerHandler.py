from __future__ import annotations

from json import dumps
from typing import Union

import settings
from common.log import logUtils as log
from common.web.requestsManager import AsyncRequestHandler
from constants import exceptions
from helpers import systemHelper


class handler(AsyncRequestHandler):
    async def get(self) -> None:
        statusCode = 400
        data: dict[str, Union[int, str]] = {"message": "unknown error"}
        try:
            # Check arguments
            if not self.checkArguments(required=["k"]):
                raise exceptions.invalidArgumentsException()

            # Check ci key
            key = self.get_argument("k")
            if not key or key != settings.APP_CI_KEY:
                raise exceptions.invalidArgumentsException()

            log.info("Ci event triggered!!")
            await systemHelper.scheduleShutdown(
                sendRestartTime=5,
                restart=False,
                message="A new Akatsuki update is available and the server will be restarted in 5 seconds. Thank you for your patience.",
            )

            # Status code and message
            statusCode = 200
            data["message"] = "ok"
        except exceptions.invalidArgumentsException:
            statusCode = 400
            data["message"] = "invalid ci key"
        finally:
            # Add status code to data
            data["status"] = statusCode

            # Send response
            self.write(dumps(data))
            self.set_status(statusCode)
