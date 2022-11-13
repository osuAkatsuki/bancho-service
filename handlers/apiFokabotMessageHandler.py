from __future__ import annotations

from json import dumps
from typing import Union

import tornado.gen
import tornado.web

import settings
from common.web import requestsManager
from constants import exceptions
from helpers import chatHelper
from objects import glob


class handler(requestsManager.asyncRequestHandler):
    @tornado.web.asynchronous
    @tornado.gen.engine
    def asyncGet(self) -> None:
        statusCode = 400
        data: dict[str, Union[int, str]] = {"message": "unknown error"}
        try:
            # Check arguments
            if not requestsManager.checkArguments(
                self.request.arguments,
                ["k", "to", "msg"],
            ):
                raise exceptions.invalidArgumentsException()

            # Check ci key
            key = self.get_argument("k")
            if not key or key != settings.APP_CI_KEY:
                raise exceptions.invalidArgumentsException()

            chatHelper.sendMessage(
                glob.BOT_NAME,
                self.get_argument("to").encode().decode("utf-8", "replace"),
                self.get_argument("msg").encode().decode("utf-8", "replace"),
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
