from __future__ import annotations

import orjson
from amplitude import BaseEvent
from amplitude import EventOptions
from amplitude import Identify

from common.constants import actions
from common.log import logger
from common.redis.pubsubs import AbstractPubSubHandler
from common.ripple import user_utils
from objects import glob
from objects import osuToken


async def handleUsernameChange(
    userID: int,
    newUsername: str,
    targetToken: osuToken.Token | None = None,
) -> None:
    try:
        oldUsername = await user_utils.get_username_from_id(userID)
        await user_utils.change_username(userID, newUsername)
        await user_utils.append_cm_notes(
            userID,
            notes=f"Username change: '{oldUsername}' -> '{newUsername}'",
        )
        if targetToken:
            await osuToken.kick(
                targetToken["token_id"],
                f"Your username has been changed to {newUsername}. Please log in again.",
                "username_change",
            )

        if glob.amplitude is not None:
            glob.amplitude.track(
                BaseEvent(
                    event_type="username_change",
                    user_id=str(userID),
                    event_properties={
                        "old_username": oldUsername,
                        "new_username": newUsername,
                        "source": "bancho-service",
                    },
                ),
            )

            identify_obj = Identify()
            identify_obj.set("username", newUsername)
            glob.amplitude.identify(identify_obj, EventOptions(user_id=str(userID)))

        logger.info(
            "Job successfully updated username",
            extra={
                "user_id": userID,
                "new_username": newUsername,
            },
        )
    except user_utils.UsernameAlreadyInUseError:
        logger.error(
            "Job failed to update username",
            extra={
                "reason": "username_exists",
                "user_id": userID,
                "new_username": newUsername,
            },
        )
        if targetToken:
            await osuToken.kick(
                targetToken["token_id"],
                "There was a critical error while trying to change your username. Please contact a developer.",
                "username_change",
            )
    except user_utils.InvalidUsernameError:
        logger.error(
            "Job failed to update username",
            extra={
                "reason": "username_invalid",
                "user_id": userID,
                "new_username": newUsername,
            },
        )
        if targetToken:
            await osuToken.kick(
                targetToken["token_id"],
                "There was a critical error while trying to change your username. Please contact a developer.",
                "username_change",
            )
    else:
        logger.info(
            "Successfully handled username change event for user",
            extra={
                "user_id": userID,
                "new_username": newUsername,
            },
        )


class ChangeUsernamePubSubHandler(AbstractPubSubHandler):
    async def handle(self, raw_data: bytes) -> None:
        data = orjson.loads(raw_data)
        assert data.keys() == {"userID", "newUsername"}

        logger.info(
            "Handling change username for user",
            extra={
                "user_id": data["userID"],
                "new_username": data["newUsername"],
            },
        )

        # Get the user's token
        if (targetToken := await osuToken.get_token_by_user_id(data["userID"])) is None:
            # If the user is offline change username immediately
            await handleUsernameChange(data["userID"], data["newUsername"])
        else:
            if targetToken["action_id"] not in {
                actions.PLAYING,
                actions.MULTIPLAYING,
            }:
                # If the user is not playing, change username and kick the user immediately
                await handleUsernameChange(
                    data["userID"],
                    data["newUsername"],
                    targetToken,
                )
            else:
                # If the user is playing, delay the username change until he submits the score
                # On submit modular, lets will send the username change request again
                # through redis once the score has been submitted
                # The check is performed on bancho logout too, so if the user disconnects
                # without submitting a score, the username gets changed on bancho logout
                await glob.redis.set(
                    f'ripple:change_username_pending:{data["userID"]}',
                    data["newUsername"],
                )

        logger.info(
            "Successfully handled change username event for user",
            extra={
                "user_id": data["userID"],
                "new_username": data["newUsername"],
            },
        )
