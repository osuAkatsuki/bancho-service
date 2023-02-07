from __future__ import annotations
from objects.osuToken import Token
from objects import osuToken

def handle(userToken: Token, _=None):
    osuToken.leaveMatch(userToken["token_id"])
