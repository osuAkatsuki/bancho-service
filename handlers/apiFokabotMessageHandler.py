from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

import settings
from constants import exceptions
from helpers import chatHelper
from objects import glob


router = APIRouter()


@router.get("/api/v1/fokabotMessage")
def send_bot_message(to: str, msg: str, key: str):
    statusCode = 400
    data: dict[str, Any] = {"message": "unknown error"}
    try:
        # Check ci key
        if key != settings.APP_CI_KEY:
            raise exceptions.invalidArgumentsException()

        chatHelper.sendMessage(glob.BOT_NAME, to, msg)

        # Status code and message
        statusCode = 200
        data["message"] = "ok"
    except exceptions.invalidArgumentsException:
        statusCode = 400
        data["message"] = "invalid parameters"
    finally:
        # Add status code to data
        data["status"] = statusCode

        return JSONResponse(content=data, status_code=statusCode)
