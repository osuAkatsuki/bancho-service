from __future__ import annotations

from constants import clientPackets
from constants import serverPackets
from objects import glob
from objects import osuToken
from objects.osuToken import Token


async def handle(userToken: Token, rawPacketData: bytes):
    # Read packet data
    packetData = clientPackets.setAwayMessage(rawPacketData)

    # Set token away message
    await osuToken.update_token(
        userToken["token_id"],
        away_message=packetData["awayMessage"],
    )

    # Send private message from Aika
    if packetData["awayMessage"] == "":
        fokaMessage = "Your away message has been reset."
    else:
        fokaMessage = f"Your away message is now: {packetData['awayMessage']}."

    await osuToken.enqueue(
        userToken["token_id"],
        serverPackets.sendMessage(
            fro=glob.BOT_NAME,
            to=userToken["username"],
            message=fokaMessage,
            fro_id=999,
        ),
    )
