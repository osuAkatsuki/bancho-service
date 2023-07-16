from __future__ import annotations

from constants import clientPackets
from helpers import chatHelper as chat
from objects.osuToken import Token

from objects import glob
from amplitude import BaseEvent
from uuid import uuid4


def handle(userToken: Token, rawPacketData: bytes):  # Channel join packet
    channel_name = clientPackets.channelJoin(rawPacketData)["channel"]
    chat.joinChannel(token_id=userToken["token_id"], channel_name=channel_name)

    insert_id = str(uuid4())
    glob.amplitude.track(
        BaseEvent(
            event_type="osu_channel_join",
            user_id=str(userToken["user_id"]),
            event_properties={
                "channel_name": channel_name,
            },
            insert_id=insert_id,
        )
    )
