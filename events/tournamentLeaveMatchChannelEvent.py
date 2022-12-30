from __future__ import annotations

from constants import clientPackets
from helpers import chatHelper as chat
from objects import match
from objects.osuToken import token


def handle(userToken: token, rawPacketData: bytes):
    packetData = clientPackets.tournamentLeaveMatchChannel(rawPacketData)
    if packetData["matchID"] not in match.get_match_ids() or not userToken.tournament:
        return
    chat.partChannel(
        token=userToken,
        channel_name=f'#multi_{packetData["matchID"]}',
        force=True,
    )
    userToken.matchID = 0 # TODO: should this be -1?
