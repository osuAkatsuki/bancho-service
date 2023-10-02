from __future__ import annotations

from amplitude import BaseEvent

from common.ripple import userUtils
from constants import clientPackets
from objects import glob
from objects.osuToken import Token


async def handle(userToken: Token, rawPacketData: bytes):  # Friend remove packet
    friend_user_id = clientPackets.addRemoveFriend(rawPacketData)["friendID"]
    await userUtils.removeFriend(userToken["user_id"], friend_user_id)

    glob.amplitude.track(
        BaseEvent(
            event_type="remove_friend",
            user_id=str(userToken["user_id"]),
            device_id=userToken["amplitude_device_id"],
            event_properties={
                "friend_user_id": friend_user_id,
                "source": "bancho-service",
            },
        ),
    )
