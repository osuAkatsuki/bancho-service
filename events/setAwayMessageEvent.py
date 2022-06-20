from constants import clientPackets, serverPackets
from objects import glob


def handle(userToken, packetData):
    # Read packet data
    packetData = clientPackets.setAwayMessage(packetData)

    # Set token away message
    userToken.awayMessage = packetData["awayMessage"]

    # Send private message from Aika
    if packetData["awayMessage"] == "":
        fokaMessage = "Your away message has been reset."
    else:
        fokaMessage = f"Your away message is now: {packetData['awayMessage']}."

    userToken.enqueue(serverPackets.sendMessage(
        fro=glob.BOT_NAME,
        to=userToken.username,
        message=fokaMessage,
        fro_id=999
    ))
