from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi import Request
from fastapi.responses import JSONResponse

from common.ripple import userUtils
from constants import exceptions
from objects import glob


router = APIRouter()


@router.get("/api/v1/isOnline")
def handler(request: Request):
    statusCode = 400
    data: dict[str, Any] = {"message": "unknown error"}
    try:
        # Check arguments
        if "u" not in request.query_params and "id" not in request.query_params:
            raise exceptions.invalidArgumentsException()

        # Get online staus
        username = None
        userID = None
        if "u" in request.query_params:
            username = userUtils.safeUsername(request.query_params["u"])
        else:
            try:
                userID = int(request.query_params["id"])
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
                assert userID is not None
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

        return JSONResponse(content=data, status_code=statusCode)
