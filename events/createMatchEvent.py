from __future__ import annotations

from common.log import logUtils as log
from constants import clientPackets
from constants import exceptions
from constants import serverPackets
from objects import glob
from objects.osuToken import token


def handle(userToken: token, rawPacketData: bytes):
    try:
        # Read packet data
        packetData = clientPackets.createMatch(rawPacketData)

        # Make sure the name is valid
        matchName = packetData["matchName"].strip()
        if not matchName:
            raise exceptions.matchCreateError()

        # Create a match object
        # TODO: Player number check
        matchID = glob.matches.createMatch(
            matchName,
            packetData["matchPassword"].strip(),
            packetData["beatmapID"],
            packetData["beatmapName"],
            packetData["beatmapMD5"],
            packetData["gameMode"],
            userToken.userID,
        )

        # Make sure the match has been created
        if matchID not in glob.matches.matches:
            raise exceptions.matchCreateError()

        with glob.matches.matches[matchID] as match:
            # Join that match
            userToken.joinMatch(matchID)

            # Give host to match creator
            match.setHost(userToken.userID)
            match.sendUpdates()
            match.changePassword(packetData["matchPassword"])
    except exceptions.matchCreateError:
        log.error("Error while creating match!")
        userToken.enqueue(serverPackets.matchJoinFail)
