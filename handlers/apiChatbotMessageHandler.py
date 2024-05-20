from __future__ import annotations

from json import dumps
from typing import Any

import settings
from common.web.requestsManager import AsyncRequestHandler
from constants import CHATBOT_USER_ID
from constants import exceptions
from helpers import chatHelper
from objects import osuToken


class handler(AsyncRequestHandler):
    async def get(self) -> None:
        statusCode = 400
        data: dict[str, Any] = {"message": "unknown error"}
        try:
            # Check arguments
            if not self.checkArguments(required=["k", "to", "msg"]):
                raise exceptions.invalidArgumentsException()

            # Check ci key
            key = self.get_argument("k")
            if not key or key != settings.APP_CI_KEY:
                raise exceptions.invalidArgumentsException()

            chatbot_token = await osuToken.get_token_by_user_id(CHATBOT_USER_ID)
            assert chatbot_token is not None

            messaging_error = await chatHelper.send_message(
                sender_token_id=chatbot_token["token_id"],
                recipient_name=(
                    self.get_argument("to").encode().decode("utf-8", "replace")
                ),
                message=self.get_argument("msg").encode().decode("utf-8", "replace"),
            )
            if messaging_error is None:
                statusCode = 200
                data["message"] = "ok"
            else:
                statusCode = 500
                data["message"] = "Failed to send message"

        except exceptions.invalidArgumentsException:
            statusCode = 400
            data["message"] = "invalid parameters"
        finally:
            # Add status code to data
            data["status"] = statusCode

            # Send response
            self.write(dumps(data))
            self.set_status(statusCode)
