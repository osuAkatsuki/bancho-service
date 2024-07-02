from __future__ import annotations

from json import dumps
from typing import Any

from common.log import logger
from common.ripple import user_utils
from common.web.requestsManager import AsyncRequestHandler
from constants import exceptions
from objects import match
from objects import osuToken
from objects import slot


class handler(AsyncRequestHandler):
    async def get(self) -> None:
        statusCode = 400
        data: dict[str, Any] = {"message": "unknown error"}
        try:
            # Check arguments
            if "u" not in self.request.arguments and "id" not in self.request.arguments:
                raise exceptions.invalidArgumentsException()

            # Get online status
            username = None
            userID = None
            if "u" in self.request.arguments:
                username = user_utils.get_safe_username(self.get_argument("u"))
            else:
                try:
                    userID = int(self.get_argument("id"))
                except:
                    raise exceptions.invalidArgumentsException()

            if not username and not userID:
                raise exceptions.invalidArgumentsException()

            userToken: osuToken.Token | None = None
            if username:
                userToken = await osuToken.get_token_by_username(username)
            elif userID:
                userToken = await osuToken.get_token_by_user_id(userID)
            else:
                raise NotImplementedError("Unknown error")

            if userToken is None:
                raise exceptions.tokenNotFoundException()

            if not (
                userToken["match_id"] is not None
                and userToken["match_slot_id"] is not None
            ):
                raise exceptions.matchNotFoundException()

            multiplayer_match = await match.get_match(userToken["match_id"])
            if multiplayer_match is None:
                logger.warning(
                    "Failed to find player's match when checking match status",
                    extra={
                        "user_id": userToken["user_id"],
                        "match_id": userToken["match_id"],
                    },
                )
                raise exceptions.matchNotFoundException()

            user_match_slot = await slot.get_slot(
                userToken["match_id"],
                userToken["match_slot_id"],
            )
            if user_match_slot is None:
                logger.warning(
                    "Failed to find player's slot when checking match status",
                    extra={
                        "user_id": userToken["user_id"],
                        "match_id": userToken["match_id"],
                        "slot_id": userToken["match_slot_id"],
                    },
                )
                raise exceptions.matchNotFoundException()

            data["result"] = {
                "match_name": multiplayer_match["match_name"],
                "match_id": userToken["match_id"],
                "slot_id": userToken["match_slot_id"],
                "game_id": multiplayer_match["current_game_id"],
                "team": user_match_slot["team"],
            }

            # Status code and message
            statusCode = 200
            data["message"] = "ok"
        except exceptions.invalidArgumentsException:
            statusCode = 400
            data["message"] = "missing required arguments"
        except exceptions.matchNotFoundException:
            statusCode = 404
            data["message"] = "match not found"
        except exceptions.tokenNotFoundException:
            statusCode = 404
            data["message"] = "online user (token) not found"
        finally:
            # Add status code to data
            data["status"] = statusCode

            # Send response
            self.write(dumps(data))
            self.set_status(statusCode)
