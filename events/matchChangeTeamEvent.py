from objects import glob
from objects.osuToken import token


def handle(userToken: token, _):
    # Make sure we are in a match
    if userToken.matchID == -1:
        return

    # Make sure the match exists
    if userToken.matchID not in glob.matches.matches:
        return

    # Change team
    with glob.matches.matches[userToken.matchID] as match:
        match.changeTeam(userToken.userID)
