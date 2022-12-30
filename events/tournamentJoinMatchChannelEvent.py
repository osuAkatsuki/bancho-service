from __future__ import annotations

from constants import clientPackets
from helpers import chatHelper as chat
from objects import match, osuToken
from objects.osuToken import Token


def handle(userToken: Token, rawPacketData: bytes):
    packetData = clientPackets.tournamentJoinMatchChannel(rawPacketData)
    if packetData["matchID"] not in match.get_match_ids() or not userToken["tournament"]:
        return

    osuToken.update_token(
        userToken["token_id"],
        match_id=packetData["matchID"],
    )

    chat.joinChannel(
        token_id=userToken["token_id"],
        channel_name=f'#multi_{packetData["matchID"]}',
        force=True,
    )
