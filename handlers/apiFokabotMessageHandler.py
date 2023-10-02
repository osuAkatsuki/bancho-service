from __future__ import annotations

from json import dumps
from typing import Union

import settings
from common.web.requestsManager import AsyncRequestHandler
from constants import exceptions
from helpers import chatHelper
from objects import tokenList


class handler(AsyncRequestHandler):
    async def get(self) -> None:
        statusCode = 400
        data: dict[str, Union[int, str]] = {"message": "unknown error"}
        try:
            # Check arguments
            if not self.checkArguments(required=["k", "to", "msg"]):
                raise exceptions.invalidArgumentsException()

            # Check ci key
            key = self.get_argument("k")
            if not key or key != settings.APP_CI_KEY:
                raise exceptions.invalidArgumentsException()

            aika_token = tokenList.getTokenFromUserID(999)
            assert aika_token is not None

            chatHelper.sendMessage(
                token_id=aika_token["token_id"],
                to=self.get_argument("to").encode().decode("utf-8", "replace"),
                message=self.get_argument("msg").encode().decode("utf-8", "replace"),
            )

            # Status code and message
            statusCode = 200
            data["message"] = "ok"
        except exceptions.invalidArgumentsException:
            statusCode = 400
            data["message"] = "invalid parameters"
        finally:
            # Add status code to data
            data["status"] = statusCode

            # Send response
            self.write(dumps(data))
            self.set_status(statusCode)
