from __future__ import annotations

from json import dumps
from typing import Union

from common.web.requestsManager import AsyncRequestHandler
from constants import exceptions
from objects import verifiedCache


class handler(AsyncRequestHandler):
    async def get(self) -> None:
        statusCode = 400
        data: dict[str, Union[int, str]] = {"message": "unknown error"}
        try:
            # Check arguments
            if not self.checkArguments(required=["u"]):
                raise exceptions.invalidArgumentsException()

            # Get userID and its verified cache thing
            # -1: Not in cache
            # 0: Not verified (multiacc)
            # 1: Verified
            userID = int(self.get_argument("u"))
            data["result"] = await verifiedCache.get(userID)

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
            self.add_header("Access-Control-Allow-Origin", "*")
            self.add_header("Content-Type", "application/json")

            # jquery meme
            output: list[str] = []
            if "callback" in self.request.arguments:
                output.extend((self.get_argument("callback"), "("))
            output.append(dumps(data))
            if "callback" in self.request.arguments:
                output.append(")")

            self.write("".join(output))
            self.set_status(statusCode)
