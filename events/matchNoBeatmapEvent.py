from __future__ import annotations

from events import matchBeatmapEvent
from objects.osuToken import token


def handle(userToken: token, rawPacketData: bytes):
    matchBeatmapEvent.handle(userToken, rawPacketData, False)
