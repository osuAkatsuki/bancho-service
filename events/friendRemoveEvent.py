from __future__ import annotations

from common.ripple import userUtils
from constants import clientPackets
from objects.osuToken import token


def handle(userToken: token, rawPacketData: bytes):  # Friend remove packet
    userUtils.removeFriend(
        userToken.userID,
        clientPackets.addRemoveFriend(rawPacketData)["friendID"],
    )
