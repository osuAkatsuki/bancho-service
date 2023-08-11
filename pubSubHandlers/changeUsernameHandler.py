from __future__ import annotations

from uuid import uuid4

from amplitude import BaseEvent
from amplitude import EventOptions
from amplitude import Identify

from common.constants import actions
from common.redis import generalPubSubHandler
from common.ripple import userUtils
from objects import glob
from objects import osuToken
from objects import tokenList


def handleUsernameChange(userID: int, newUsername: str, targetToken=None):
    try:
        oldUsername = userUtils.getUsername(userID)
        userUtils.changeUsername(userID, newUsername=newUsername)
        userUtils.appendNotes(
            userID,
            f"Username change: '{oldUsername}' -> '{newUsername}'",
        )
        if targetToken:
            osuToken.kick(
                targetToken["token_id"],
                f"Your username has been changed to {newUsername}. Please log in again.",
                "username_change",
            )

        # XXX: disabled this 2023-07-28 as it seems strange - this is not necessarily
        # an action triggered by the user themselves; feels weird to attribute it to them
        # insert_id = str(uuid4())
        # glob.amplitude.track(
        #     BaseEvent(
        #         event_type="username_change",
        #         user_id=str(userID),
        #         event_properties={
        #             "old_username": oldUsername,
        #             "new_username": newUsername,
        #             "source": "bancho-service",
        #         },
        #         insert_id=insert_id,
        #     )
        # )

        identify_obj = Identify()
        identify_obj.set("username", newUsername)
        glob.amplitude.identify(identify_obj, EventOptions(user_id=str(userID)))

    except userUtils.usernameAlreadyInUseError:
        # log.rap(999, "Username change: {} is already in use!", through="Bancho")
        if targetToken:
            osuToken.kick(
                targetToken["token_id"],
                "There was a critical error while trying to change your username. Please contact a developer.",
                "username_change",
            )
    except userUtils.invalidUsernameError:
        # log.rap(999, "Username change: {} is not a valid username!", through="Bancho")
        if targetToken:
            osuToken.kick(
                targetToken["token_id"],
                "There was a critical error while trying to change your username. Please contact a developer.",
                "username_change",
            )


class handler(generalPubSubHandler.generalPubSubHandler):
    def __init__(self):
        super().__init__()
        self.structure = {"userID": 0, "newUsername": ""}

    def handle(self, data):
        if not (data := super().parseData(data)):
            return

        # Get the user's token
        if (targetToken := tokenList.getTokenFromUserID(data["userID"])) is None:
            # If the user is offline change username immediately
            handleUsernameChange(data["userID"], data["newUsername"])
        else:
            if targetToken["irc"] or targetToken["action_id"] not in {
                actions.PLAYING,
                actions.MULTIPLAYING,
            }:
                # If the user is online and he's connected through IRC or he's not playing,
                # change username and kick the user immediately
                handleUsernameChange(data["userID"], data["newUsername"], targetToken)
            else:
                # If the user is playing, delay the username change until he submits the score
                # On submit modular, lets will send the username change request again
                # through redis once the score has been submitted
                # The check is performed on bancho logout too, so if the user disconnects
                # without submitting a score, the username gets changed on bancho logout
                glob.redis.set(
                    f'ripple:change_username_pending:{data["userID"]}',
                    data["newUsername"],
                )
