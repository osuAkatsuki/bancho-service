from __future__ import annotations

from common.log import logUtils as log
from constants import clientPackets
from constants import exceptions
from constants import serverPackets
from objects import match
from objects import matchList, osuToken

from redlock import RedLock


def handle(token: osuToken.Token, rawPacketData: bytes):
    try:
        # Read packet data
        packetData = clientPackets.createMatch(rawPacketData)

        # Make sure the name is valid
        match_name = packetData["matchName"].strip()
        if not match_name:
            raise exceptions.matchCreateError()

        # Create a match object
        # TODO: Player number check
        match_id = matchList.createMatch(
            match_name,
            packetData["matchPassword"].strip(),
            packetData["beatmapID"],
            packetData["beatmapName"],
            packetData["beatmapMD5"],
            packetData["gameMode"],
            token["user_id"],
        )

        # Make sure the match has been created
        multiplayer_match = match.get_match(match_id)
        if multiplayer_match is None:
            raise exceptions.matchCreateError()

        # Join that match
        osuToken.joinMatch(token["token_id"], match_id)

        # Give host to match creator
        match.setHost(match_id, token["user_id"])
        match.sendUpdates(match_id)
        match.changePassword(match_id, packetData["matchPassword"])
    except exceptions.matchCreateError:
        log.error("Error while creating match!")
        osuToken.enqueue(token["token_id"], serverPackets.matchJoinFail)
