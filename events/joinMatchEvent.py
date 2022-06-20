from common.log import logUtils as log
from constants import clientPackets, exceptions, serverPackets
from objects import glob


def handle(userToken, packetData):
    # read packet data
    packetData = clientPackets.joinMatch(packetData)
    matchID = packetData["matchID"]
    password = packetData["password"]

    # Get match from ID
    try:
        # Make sure the match exists
        if matchID not in glob.matches.matches:
            return

        # Check password
        with glob.matches.matches[matchID] as match:
            if match.matchPassword not in ("", password):
                raise exceptions.matchWrongPasswordException()

            # Password is correct, join match
            userToken.joinMatch(matchID)
    except exceptions.matchWrongPasswordException:
        userToken.enqueue(serverPackets.matchJoinFail)
        log.warning(f"{userToken.username} has tried to join a mp room, but he typed the wrong password.")
