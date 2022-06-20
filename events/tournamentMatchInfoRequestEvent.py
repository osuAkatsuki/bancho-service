from constants import clientPackets
from objects import glob


def handle(userToken, packetData):
    packetData = clientPackets.tournamentMatchInfoRequest(packetData)
    if (
        packetData["matchID"] not in glob.matches.matches or
        not userToken.tournament
    ):
        return
    with glob.matches.matches[packetData["matchID"]] as m:
        userToken.enqueue(m.matchDataCache)
