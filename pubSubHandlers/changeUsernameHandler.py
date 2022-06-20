from common.constants import actions
from common.log import logUtils as log
from common.redis import generalPubSubHandler
from common.ripple import userUtils
from objects import glob


def handleUsernameChange(userID: int, newUsername: str, targetToken = None):
    try:
        oldUsername = userUtils.getUsername(userID)
        userUtils.changeUsername(userID, newUsername=newUsername)
        userUtils.appendNotes(userID, f"Username change: '{oldUsername}' -> '{newUsername}'")
        if targetToken:
            targetToken.kick(f"Your username has been changed to {newUsername}. Please log in again.", "username_change")
    except userUtils.usernameAlreadyInUseError:
        # log.rap(999, "Username change: {} is already in use!", through="Bancho")
        if targetToken:
            targetToken.kick("There was a critical error while trying to change your username. Please contact a developer.", "username_change_fail")
    except userUtils.invalidUsernameError:
        # log.rap(999, "Username change: {} is not a valid username!", through="Bancho")
        if targetToken:
            targetToken.kick("There was a critical error while trying to change your username. Please contact a developer.", "username_change_fail")

class handler(generalPubSubHandler.generalPubSubHandler):
    def __init__(self):
        super().__init__()
        self.structure = {
            "userID": 0,
            "newUsername": ""
        }

    def handle(self, data):
        if not (data := super().parseData(data)):
            return

        # Get the user's token
        if (targetToken := glob.tokens.getTokenFromUserID(data["userID"])) is None:
            # If the user is offline change username immediately
            handleUsernameChange(data["userID"], data["newUsername"])
        else:
            if targetToken.irc or targetToken.actionID not in {actions.PLAYING, actions.MULTIPLAYING}:
                # If the user is online and he's connected through IRC or he's not playing,
                # change username and kick the user immediately
                handleUsernameChange(data["userID"], data["newUsername"], targetToken)
            else:
                # If the user is playing, delay the username change until he submits the score
                # On submit modular, lets will send the username change request again
                # through redis once the score has been submitted
                # The check is performed on bancho logout too, so if the user disconnects
                # without submitting a score, the username gets changed on bancho logout
                glob.redis.set(f'ripple:change_username_pending:{data["userID"]}', data["newUsername"])
