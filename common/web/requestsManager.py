from __future__ import annotations

import tornado.web


class AsyncRequestHandler(tornado.web.RequestHandler):
    """A thin wrapper around tornado.web.RequestHandler to add some useful methods."""

    def getRequestIP(self):
        if "CF-Connecting-IP" in self.request.headers:
            return self.request.headers.get("CF-Connecting-IP")
        elif "X-Forwarded-For" in self.request.headers:
            return self.request.headers.get("X-Forwarded-For")
        else:
            return self.request.remote_ip

    def checkArguments(self, required: list[str]) -> bool:
        return all(a in self.request.arguments for a in required)
