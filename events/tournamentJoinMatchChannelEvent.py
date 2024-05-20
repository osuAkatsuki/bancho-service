from __future__ import annotations

from constants import clientPackets
from helpers import chatHelper as chat
from objects import match
from objects import osuToken
from objects.osuToken import Token


async def handle(userToken: Token, rawPacketData: bytes) -> None:
    if not userToken["tournament"]:
        return

    packetData = clientPackets.tournamentJoinMatchChannel(rawPacketData)

    match_id = packetData["matchID"]

    multiplayer_match = await match.get_match(match_id)
    if multiplayer_match is None:
        return

    await chat.join_channel(
        token_id=userToken["token_id"],
        channel_name=f"#mp_{match_id}",
        allow_instance_channels=True,
    )

    await osuToken.update_token(userToken["token_id"], match_id=match_id)
