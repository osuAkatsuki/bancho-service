from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from objects import glob


router = APIRouter()


@router.get("/api/v1/onlineUsers")
def get_online_users():
    statusCode = 400
    data: dict[str, Any] = {"message": "unknown error"}
    try:
        online_users = glob.redis.get("ripple:online_users")
        assert online_users is not None

        data["result"] = int(online_users.decode("utf-8"))
        data["message"] = "ok"
        statusCode = 200
    finally:
        data["status"] = statusCode

        return JSONResponse(content=data, status_code=statusCode)
