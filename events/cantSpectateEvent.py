from common.log import logUtils as log
from constants import exceptions, serverPackets
from objects import glob
from objects.osuToken import token


def handle(userToken: token, _):
    try:
        # We don't have the beatmap, we can't spectate
        if (
            userToken.spectating is None
            or userToken.spectating not in glob.tokens.tokens
        ):
            raise exceptions.tokenNotFoundException()

        # Send the packet to host
        glob.tokens.tokens[userToken.spectating].enqueue(
            serverPackets.noSongSpectator(userToken.userID)
        )
    except exceptions.tokenNotFoundException:
        # Stop spectating if token not found
        log.warning("Spectator can't spectate: token not found.")
        userToken.stopSpectating()
