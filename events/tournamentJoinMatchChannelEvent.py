from __future__ import annotations

from constants import clientPackets
from helpers import chatHelper as chat
from objects import glob
from objects.osuToken import token


def handle(userToken: token, rawPacketData: bytes):
    packetData = clientPackets.tournamentJoinMatchChannel(rawPacketData)
    if packetData["matchID"] not in glob.matches.matches or not userToken.tournament:
        return
    userToken.matchID = packetData["matchID"]
    chat.joinChannel(
        token=userToken,
        channel=f'#multi_{packetData["matchID"]}',
        force=True,
    )
