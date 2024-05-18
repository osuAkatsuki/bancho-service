from __future__ import annotations

from amplitude import BaseEvent

from constants import clientPackets
from helpers import chatHelper as chat
from objects import glob
from objects.osuToken import Token


async def handle(userToken: Token, rawPacketData: bytes) -> None:
    # Send private message packet
    packetData = clientPackets.sendPrivateMessage(rawPacketData)
    await chat.send_message(
        sender_token_id=userToken["token_id"],
        recipient_name=packetData["to"],
        message=packetData["message"],
    )

    if glob.amplitude is not None:
        glob.amplitude.track(
            BaseEvent(
                event_type="osu_private_message",
                user_id=str(userToken["user_id"]),
                device_id=userToken["amplitude_device_id"],
                event_properties={
                    "recipient": packetData["to"],
                    # NOTE: intentionally not logging the message here
                    "source": "bancho-service",
                },
            ),
        )
