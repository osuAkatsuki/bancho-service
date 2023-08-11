from __future__ import annotations

from common.log import logUtils as log
from constants import serverPackets
from objects import stream
from objects import streamList
from objects.osuToken import Token


def handle(userToken: Token, rawPacketData: bytes):
    # Send spectator frames to every spectator
    streamName = f"spect/{userToken['user_id']}"
    streamList.broadcast(streamName, serverPackets.spectatorFrames(rawPacketData[7:]))
    log.debug(
        f"Broadcasting {userToken['user_id']}'s frames to {stream.getClientCount(streamName)} clients.",
    )
