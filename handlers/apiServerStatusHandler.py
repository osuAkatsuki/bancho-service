from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from objects import glob


router = APIRouter()


@router.get("/api/v1/serverStatus")
def get_server_status():
    statusCode = 400
    data: dict[str, Any] = {"message": "unknown error"}
    try:
        data["result"] = -1 if glob.restarting else 1
        statusCode = 200
        data["message"] = "ok"
    finally:
        data["status"] = statusCode

        return JSONResponse(content=data, status_code=statusCode)
