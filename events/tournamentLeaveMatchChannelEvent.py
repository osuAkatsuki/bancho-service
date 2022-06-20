from constants import clientPackets
from helpers import chatHelper as chat
from objects import glob


def handle(userToken, packetData):
    packetData = clientPackets.tournamentLeaveMatchChannel(packetData)
    if (
        packetData["matchID"] not in glob.matches.matches or
        not userToken.tournament
    ):
        return
    chat.partChannel(token=userToken, channel=f'#multi_{packetData["matchID"]}', force=True)
    userToken.matchID = 0
