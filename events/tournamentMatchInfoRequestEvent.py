from constants import clientPackets
from objects import glob
from objects.osuToken import token


def handle(userToken: token, rawPacketData: bytes):
    packetData = clientPackets.tournamentMatchInfoRequest(rawPacketData)
    if packetData["matchID"] not in glob.matches.matches or not userToken.tournament:
        return
    with glob.matches.matches[packetData["matchID"]] as m:
        userToken.enqueue(m.matchDataCache)
