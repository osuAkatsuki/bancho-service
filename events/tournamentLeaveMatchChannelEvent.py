from __future__ import annotations

from constants import clientPackets
from helpers import chatHelper as chat
from objects import match
from objects import osuToken
from objects.osuToken import Token


async def handle(userToken: Token, rawPacketData: bytes) -> None:
    packetData = clientPackets.tournamentLeaveMatchChannel(rawPacketData)
    if (
        packetData["matchID"] not in await match.get_match_ids()
        or not userToken["tournament"]
    ):
        return

    await chat.part_channel(
        token_id=userToken["token_id"],
        channel_name=f'#mp_{packetData["matchID"]}',
        allow_instance_channels=True,
    )

    await osuToken.update_token(
        userToken["token_id"],
        match_id=None,
    )
