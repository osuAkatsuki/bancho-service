from __future__ import annotations

from amplitude import BaseEvent

from common.log import logUtils as log
from constants import exceptions
from objects import glob
from objects import osuToken


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

        glob.amplitude.track(
            BaseEvent(
                event_type="stop_spectating",
                user_id=str(userToken["user_id"]),
                device_id=userToken["amplitude_device_id"],
                event_properties={
                    "host_user_id": targetToken["user_id"],
                    "host_username": targetToken["username"],
                    "host_country": targetToken["country"],
                    "host_game_mode": targetToken["game_mode"],
                    "source": "bancho-service",
                },
            ),
        )

    except exceptions.tokenNotFoundException:
        # Stop spectating if token not found
        log.warning("Spectator stop: host token not found.")
