from __future__ import annotations

import asyncio
import logging
import httpx
from os import name
from typing import Optional

import settings
from common.ripple import userUtils
from common.web.discord import Webhook
from objects import glob

ENDL = "\n" if name == "posix" else "\r\n"

RETRY_INTERVAL = 8
MAX_RETRIES = 10

DISCORD_CHANNELS = {
    "ac_general": settings.WEBHOOK_AC_GENERAL,
    "ac_confidential": settings.WEBHOOK_AC_CONFIDENTIAL,
}
DISCORD_WEBHOOK_EMBED_COLOR = 0x542CB8


async def send_rap_log_as_discord_webhook(message: str, discord_channel: str) -> None:
    """Log a message to the provided discord channel, if configured."""

    if discord_channel is not None:
        discord_webhook_url = DISCORD_CHANNELS.get(discord_channel)
        if discord_webhook_url is None:
            logging.error(
                "Attempted to send webhook to an unknown discord channel",
                extra={"discord_channel": discord_channel},
            )
            return

        embed = Webhook(discord_webhook_url, color=DISCORD_WEBHOOK_EMBED_COLOR)
        embed.add_field(name="** **", value=message)
        embed.set_footer(text="Akatsuki bancho-service")
        embed.set_thumbnail("https://akatsuki.gg/static/logos/logo.png")

        for _ in range(MAX_RETRIES):
            try:
                await embed.post()
                break
            except (httpx.NetworkError, httpx.TimeoutException):
                await asyncio.sleep(RETRY_INTERVAL)
                continue
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 429:
                    await asyncio.sleep(RETRY_INTERVAL)
                    continue
                else:
                    raise


async def send_rap_log(
    user_id: int,
    message: str,
    discord_channel: Optional[str] = None,
    admin: str = "Aika",
) -> None:
    """
    Log a message to Admin Logs.
    :param userID: admin user ID
    :param message: message content, without username
    :param discord: if True, send the message to discord
    :param admin: admin who submitted this. Default: Aika
    :return:
    """
    await glob.db.execute(
        "INSERT INTO rap_logs (id, userid, text, datetime, through) "  # could be admin in db too?
        "VALUES (NULL, %s, %s, UNIX_TIMESTAMP(), %s)",
        [user_id, message, admin],
    )
    if discord_channel is not None:
        await asyncio.create_task(
            send_rap_log_as_discord_webhook(
                message=f"{userUtils.getUsername(user_id)} {message}",
                discord_channel=discord_channel,
            ),
        )
