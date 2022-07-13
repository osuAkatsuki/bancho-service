from events import matchBeatmapEvent
from objects.osuToken import token


def handle(userToken: token, rawPacketData: bytes):
    matchBeatmapEvent.handle(userToken, rawPacketData, False)
