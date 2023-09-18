from __future__ import annotations

from json import dumps
from typing import Union

from common.ripple import userUtils
from common.web.requestsManager import AsyncRequestHandler
from constants import exceptions
from objects import tokenList


class handler(AsyncRequestHandler):
    async def get(self) -> None:
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
                        True if tokenList.getTokenFromUsername(username) else False
                    )
                else:
                    data["result"] = (
                        True if tokenList.getTokenFromUserID(userID) else False
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
