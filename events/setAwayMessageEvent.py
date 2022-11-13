from __future__ import annotations

from constants import clientPackets
from constants import serverPackets
from objects import glob
from objects.osuToken import token


def handle(userToken: token, rawPacketData: bytes):
    # Read packet data
    packetData = clientPackets.setAwayMessage(rawPacketData)

    # Set token away message
    userToken.awayMessage = packetData["awayMessage"]

    # Send private message from Aika
    if packetData["awayMessage"] == "":
        fokaMessage = "Your away message has been reset."
    else:
        fokaMessage = f"Your away message is now: {packetData['awayMessage']}."

    userToken.enqueue(
        serverPackets.sendMessage(
            fro=glob.BOT_NAME,
            to=userToken.username,
            message=fokaMessage,
            fro_id=999,
        ),
    )
