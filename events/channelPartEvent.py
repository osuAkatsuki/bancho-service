from __future__ import annotations

from amplitude import BaseEvent

from constants import clientPackets
from helpers import chatHelper as chat
from objects import glob
from objects.osuToken import Token


async def handle(userToken: Token, rawPacketData: bytes):
    channel_name = clientPackets.channelJoin(rawPacketData)["channel"]
    await chat.partChannel(token_id=userToken["token_id"], channel_name=channel_name)

    if glob.amplitude is not None:
        glob.amplitude.track(
            BaseEvent(
                event_type="osu_channel_leave",
                user_id=str(userToken["user_id"]),
                device_id=userToken["amplitude_device_id"],
                event_properties={
                    "channel_name": channel_name,
                    "source": "bancho-service",
                },
            ),
        )
