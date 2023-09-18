from __future__ import annotations

from common.log import logUtils as log


class asyncRequestHandler(tornado.web.RequestHandler):
    """
    Tornado asynchronous request handler
    create a class that extends this one (requestHelper.asyncRequestHandler)
    use asyncGet() and asyncPost() instead of get() and post().
    Done. I'm not kidding.
    """

    def getRequestIP(self):
        """
        Return CF-Connecting-IP (request IP when under cloudflare, you have to configure nginx to enable that)
        If that fails, return X-Forwarded-For (request IP when not under Cloudflare)
        if everything else fails, return remote IP

        :return: Client IP address
        """
        return getRequestIP(self.request)

    def checkArguments(self, required: list[str]) -> bool:
        return checkArguments(self.request.arguments, required)


def getRequestIP(request):
    """
    Return CF-Connecting-IP (request IP when under cloudflare, you have to configure nginx to enable that)
    If that fails, return X-Forwarded-For (request IP when not under Cloudflare)
    if everything else fails, return remote IP

    :return: Client IP address
    """
    if "CF-Connecting-IP" in request.headers:
        return request.headers.get("CF-Connecting-IP")
    elif "X-Forwarded-For" in request.headers:
        return request.headers.get("X-Forwarded-For")
    else:
        return request.remote_ip


def checkArguments(arguments, requiredArguments):
    """
    Check that every requiredArguments elements are in arguments

    :param arguments: full argument list, from tornado
    :param requiredArguments: required arguments list
    :return: True if all arguments are passed, False if not
    """
    for i in requiredArguments:
        if i not in arguments:
            return False
    return True


def printArguments(t):
    """
    Print passed arguments, for debug purposes

    :param t: tornado object (self)
    """
    msg = "ARGS::"
    for i in t.request.arguments:
        msg += f"{i}={t.get_argument(i)}\r\n"
    log.debug(msg)
