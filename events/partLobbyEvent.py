from __future__ import annotations

from helpers import chatHelper as chat


def handle(userToken, _):
    # Remove user from users in lobby
    userToken.leaveStream("lobby")

    # Part lobby channel
    # Done automatically by the client
    chat.partChannel(channel="#lobby", token=userToken, kick=True)
