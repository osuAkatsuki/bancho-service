from __future__ import annotations

from requests import RequestException

import settings
from common.web.discord import Webhook
from objects import glob


class schiavo:
    """
    Schiavo Bot class
    """

    def __init__(self, botURL=None, prefix="", maxRetries=5):
        """
        Initialize a new schiavo bot instance

        :param botURL: schiavo api url. oepsie i changed this a lot.
        :param maxRetries: max retries if api request fail. 0 = don't retry.
        """
        self.maxRetries = maxRetries

    def sendMessage(self, message, botURL):
        """
        Send a generic message through schiavo api

        :param channel: api channel.
        :param message: message content.
        :param customParams: Let all hell break loose
        :return:

        Let's call it 50% spaghetti code.. Deal..?
        """
        if not botURL:
            return

        embed = Webhook(botURL, color=0x542CB8)
        embed.add_field(name="** **", value=message)
        embed.set_footer(text=f"Akatsuki Anticheat")
        embed.set_thumbnail("https://akatsuki.pw/static/logos/logo.png")

        for _ in range(self.maxRetries):
            try:
                embed.post()
                break
            except RequestException:
                continue

    # Anticheat webhooks
    def sendACGeneral(self, message):  # GMT+
        """
        Send a message to Anticheat's #general

        :param message: message content.
        :return:
        """
        self.sendMessage(message, settings.WEBHOOK_AC_GENERAL)

    def sendACConfidential(self, message):  # cmyui only
        """
        Send a message to Anticheat's #confidential

        :param message: message content.
        :return:
        """
        self.sendMessage(message, settings.WEBHOOK_AC_CONFIDENTIAL)
