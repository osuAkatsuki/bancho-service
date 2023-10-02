from __future__ import annotations

from events import matchBeatmapEvent
from objects.osuToken import Token


async def handle(userToken: Token, rawPacketData: bytes):
    await matchBeatmapEvent.handle(userToken, rawPacketData, True)
