from __future__ import annotations

from json import dumps
from typing import Union

import tornado.gen
import tornado.web

from common.ripple import userUtils
from common.sentry import sentry
from common.web import requestsManager
from constants import exceptions
from objects import glob


class handler(requestsManager.asyncRequestHandler):
    @tornado.web.asynchronous
    @tornado.gen.engine
    @sentry.captureTornado
    def asyncGet(self) -> None:
        statusCode = 400
        data: dict[str, Union[bool, str]] = {"message": "unknown error"}
        try:
            # Check arguments
            if "u" not in self.request.arguments and "id" not in self.request.arguments:
                raise exceptions.invalidArgumentsException()

            # Get online staus
            username = None
            userID = None
            if "u" in self.request.arguments:
                username = userUtils.safeUsername(self.get_argument("u"))
            else:
                try:
                    userID = int(self.get_argument("id"))
                except:
                    raise exceptions.invalidArgumentsException()

            if not username and not userID:
                data["result"] = False
            else:
                if username:
                    data["result"] = (
                        True
                        if glob.tokens.getTokenFromUsername(username, safe=True)
                        else False
                    )
                else:
                    data["result"] = (
                        True if glob.tokens.getTokenFromUserID(userID) else False
                    )

            # Status code and message
            statusCode = 200
            data["message"] = "ok"
        except exceptions.invalidArgumentsException:
            statusCode = 400
            data["message"] = "missing required arguments"
        finally:
            # Add status code to data
            data["status"] = statusCode

            # Send response
            self.write(dumps(data))
            self.set_status(statusCode)
