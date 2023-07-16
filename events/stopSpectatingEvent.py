from __future__ import annotations
from constants import exceptions
from objects import osuToken

from amplitude import BaseEvent
from objects import glob
from common.log import logUtils as log
from uuid import uuid4

def handle(userToken: osuToken.Token, _=None):
    try:
        # User must be spectating someone
        if userToken["spectating_user_id"] is None:
            return

        # Get host token
        targetToken = osuToken.get_token_by_user_id(userToken["spectating_user_id"])
        if targetToken is None:
            raise exceptions.tokenNotFoundException

        osuToken.stopSpectating(userToken["token_id"])

        insert_id = str(uuid4())
        glob.amplitude.track(
            BaseEvent(
                event_type="stop_spectating",
                user_id=str(userToken["user_id"]),
                event_properties={
                    "host_user_id": targetToken["user_id"],
                    "host_username": targetToken["username"],
                    "host_country": targetToken["country"],
                    "host_game_mode": targetToken["game_mode"],
                },
                insert_id=insert_id,
            )
        )

    except exceptions.tokenNotFoundException:
        # Stop spectating if token not found
        log.warning("Spectator stop: host token not found.")
