from __future__ import annotations

from common.log import logUtils as log
from constants import serverPackets
from objects import stream,streamList
from objects.osuToken import token


def handle(userToken: token, rawPacketData: bytes):
    # Send spectator frames to every spectator
    streamName = f"spect/{userToken.userID}"
    streamList.broadcast(streamName, serverPackets.spectatorFrames(rawPacketData[7:]))
    log.debug(
        f"Broadcasting {userToken.userID}'s frames to {stream.getClientCount(streamName)} clients.",
    )
