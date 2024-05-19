from __future__ import annotations

from typing import Optional
from uuid import uuid4

import tornado.web

from common.log import logger


class AsyncRequestHandler(tornado.web.RequestHandler):  # type: ignore[misc]
    """A thin wrapper around tornado.web.RequestHandler to add some useful methods."""

    def prepare(self) -> None:
        request_id = self.request.headers.get("X-Request-ID", None) or str(uuid4())
        logger.add_context(request_id=request_id)

    def getRequestIP(self) -> Optional[str]:
        if "CF-Connecting-IP" in self.request.headers:
            return str(self.request.headers.get("CF-Connecting-IP"))
        elif "X-Forwarded-For" in self.request.headers:
            return str(self.request.headers.get("X-Forwarded-For"))
        else:
            return str(self.request.remote_ip)

    def checkArguments(self, required: list[str]) -> bool:
        return all(a in self.request.arguments for a in required)
