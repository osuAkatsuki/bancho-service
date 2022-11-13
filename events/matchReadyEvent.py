from __future__ import annotations

from objects import glob


def handle(userToken, _):
    if userToken.matchID not in glob.matches.matches:
        return

    with glob.matches.matches[userToken.matchID] as match:
        # Get our slotID and change ready status
        slotID = match.getUserSlotID(userToken.userID)
        if slotID is not None:
            match.toggleSlotReady(slotID)

        # If this is a tournament match, we should send the current status of ready
        # players.
        if match.isTourney:
            match.sendReadyStatus()
