from objects import glob


def handle(userToken, _, has):
    # Make sure we are in a match
    if userToken.matchID == -1:
        return

    # Make sure the match exists
    if userToken.matchID not in glob.matches.matches:
        return

    # Set has beatmap/no beatmap
    with glob.matches.matches[userToken.matchID] as match:
        match.userHasBeatmap(userToken.userID, has)
