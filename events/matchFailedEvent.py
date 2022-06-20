from objects import glob


def handle(userToken, _):
    # Make sure we are in a match
    if userToken.matchID == -1:
        return

    # Make sure the match exists
    if userToken.matchID not in glob.matches.matches:
        return

    # Fail user
    with glob.matches.matches[userToken.matchID] as match:
        match.playerFailed(userToken.userID)
