from __future__ import annotations

from constants import clientPackets
from helpers import chatHelper as chat
from objects.osuToken import Token

from objects import glob
from amplitude import BaseEvent
from uuid import uuid4


def handle(userToken: Token, rawPacketData: bytes):
    # Send public message packet
    packetData = clientPackets.sendPublicMessage(rawPacketData)
    chat.sendMessage(
        token_id=userToken["token_id"],
        to=packetData["to"],
        message=packetData["message"],
    )

    insert_id = str(uuid4())
    glob.amplitude.track(
        BaseEvent(
            event_type="osu_public_message",
            user_id=str(userToken["user_id"]),
            device_id=userToken["amplitude_device_id"],
            event_properties={
                "recipient": packetData["to"],
                "message": packetData["message"],
                "source": "bancho-service",
            },
            insert_id=insert_id,
        )
    )
