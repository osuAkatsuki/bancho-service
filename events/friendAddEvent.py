from __future__ import annotations

from common.ripple import userUtils
from constants import clientPackets
from objects.osuToken import Token


def handle(userToken: Token, rawPacketData: bytes):  # Friend add packet
    userUtils.addFriend(
        userToken["user_id"],
        clientPackets.addRemoveFriend(rawPacketData)["friendID"],
    )
