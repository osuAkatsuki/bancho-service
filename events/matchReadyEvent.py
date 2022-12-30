from __future__ import annotations

from objects import match
from objects.osuToken import token

from redlock import RedLock

def handle(userToken: token, _):
    multiplayer_match = match.get_match(userToken.matchID)
    if multiplayer_match is None:
        return

    with RedLock(
        f"{match.make_key(userToken.matchID)}:lock",
        retry_delay=50,
        retry_times=20,
    ):
        # Get our slotID and change ready status
        slot_id = match.getUserSlotID(multiplayer_match["match_id"], userToken.userID)
        if slot_id is not None:
            match.toggleSlotReady(multiplayer_match["match_id"], slot_id)

        # If this is a tournament match, we should send the current status of ready
        # players.
        if multiplayer_match["is_tourney"]:
            match.sendReadyStatus(multiplayer_match["match_id"])
