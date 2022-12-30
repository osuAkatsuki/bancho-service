from __future__ import annotations

from common.ripple import userUtils
from constants import clientPackets
from objects.osuToken import Token


def handle(userToken: Token, rawPacketData: bytes):  # Friend remove packet
    userUtils.removeFriend(
        userToken["user_id"],
        clientPackets.addRemoveFriend(rawPacketData)["friendID"],
    )
