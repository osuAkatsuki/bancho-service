from objects import glob


def handle(userToken, _):
    # Make sure we are in a match
    if userToken.matchID == -1:
        return

    # Make sure the match exists
    if userToken.matchID not in glob.matches.matches:
        return

    # Set our match complete
    with glob.matches.matches[userToken.matchID] as match:
        match.playerCompleted(userToken.userID)
