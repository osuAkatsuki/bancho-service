from __future__ import annotations

from events import matchBeatmapEvent
from objects.osuToken import Token


def handle(userToken: Token, rawPacketData: bytes):
    matchBeatmapEvent.handle(userToken, rawPacketData, True)
