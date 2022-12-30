from __future__ import annotations

from common.log import logUtils as log
from constants import clientPackets
from constants import exceptions
from constants import serverPackets
from objects import glob, match
from objects.osuToken import token

from redlock import RedLock


def handle(userToken: token, rawPacketData: bytes):
    try:
        # Read packet data
        packetData = clientPackets.createMatch(rawPacketData)

        # Make sure the name is valid
        match_name = packetData["matchName"].strip()
        if not match_name:
            raise exceptions.matchCreateError()

        # Create a match object
        # TODO: Player number check
        match_id = glob.matches.createMatch(
            match_name,
            packetData["matchPassword"].strip(),
            packetData["beatmapID"],
            packetData["beatmapName"],
            packetData["beatmapMD5"],
            packetData["gameMode"],
            userToken.userID,
        )

        # Make sure the match has been created
        multiplayer_match = match.get_match(match_id)
        if multiplayer_match is None:
            raise exceptions.matchCreateError()

        with RedLock(
            f"{match.make_key(match_id)}:lock",
            retry_delay=50,
            retry_times=20,
        ):
            # Join that match
            userToken.joinMatch(match_id)

            # Give host to match creator
            match.setHost(match_id, userToken.userID)
            match.sendUpdates(match_id)
            match.changePassword(match_id, packetData["matchPassword"])
    except exceptions.matchCreateError:
        log.error("Error while creating match!")
        userToken.enqueue(serverPackets.matchJoinFail)
