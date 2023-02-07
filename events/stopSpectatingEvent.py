from __future__ import annotations
from objects import osuToken

def handle(userToken: osuToken.Token, _=None):
    osuToken.stopSpectating(userToken["token_id"])
