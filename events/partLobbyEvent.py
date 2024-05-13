from __future__ import annotations

from helpers import chatHelper as chat
from objects import osuToken
from objects.osuToken import Token


async def handle(userToken: Token, rawPacketData: bytes) -> None:
    # Remove user from users in lobby
    await osuToken.leaveStream(userToken["token_id"], "lobby")

    # Part lobby channel
    # Done automatically by the client
    await chat.part_channel(
        channel_name="#lobby",
        token_id=userToken["token_id"],
        notify_user_of_kick=True,
    )
