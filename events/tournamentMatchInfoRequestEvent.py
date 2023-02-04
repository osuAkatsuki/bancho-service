from __future__ import annotations

from constants import clientPackets
from objects import match
from objects import osuToken
from objects.osuToken import Token
from constants import serverPackets

from redlock import RedLock

def handle(userToken: Token, rawPacketData: bytes):
    packetData = clientPackets.tournamentMatchInfoRequest(rawPacketData)

    match_id = packetData["matchID"]
    multiplayer_match = match.get_match(match_id)
    if multiplayer_match is None or not userToken.tournament:
        return

    with RedLock(
        f"{match.make_key(match_id)}:lock",
        retry_delay=100, # ms
        retry_times=500,
    ):
        packet_data = serverPackets.updateMatch(match_id)
        if packet_data is None:
            # TODO: is this correct behaviour?
            # ripple was doing this before the stateless refactor,
            # but i'm pretty certain the osu! client won't like this.
            osuToken.enqueue(userToken["token_id"], b"")
            return None

        osuToken.enqueue(userToken["token_id"], packet_data)
