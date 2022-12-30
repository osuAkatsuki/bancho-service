from __future__ import annotations

from helpers import chatHelper as chat
from objects.osuToken import Token
from objects import osuToken


def handle(userToken: Token, _):
    # Remove user from users in lobby
    osuToken.leaveStream(userToken["token_id"], "lobby")

    # Part lobby channel
    # Done automatically by the client
    chat.partChannel(channel_name="#lobby", token_id=userToken["token_id"], kick=True)
