from common.log import logUtils as log
from constants import serverPackets
from objects import glob
from objects.osuToken import token


def handle(userToken: token, rawPacketData: bytes):
    # Send spectator frames to every spectator
    streamName = f"spect/{userToken.userID}"
    glob.streams.broadcast(streamName, serverPackets.spectatorFrames(rawPacketData[7:]))
    log.debug(
        f"Broadcasting {userToken.userID}'s frames to {len(glob.streams.streams[streamName].clients)} clients."
    )
