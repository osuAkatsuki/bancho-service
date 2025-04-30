from __future__ import annotations

import asyncio

import httpx

import settings
from common import job_scheduling
from common.log import logger
from common.ripple import user_utils
from common.web.discord import Webhook
from objects import glob

RETRY_INTERVAL = 8
MAX_RETRIES = 10

DISCORD_CHANNELS = {"ac_general": settings.WEBHOOK_AC_GENERAL}
DISCORD_WEBHOOK_EMBED_COLOR = 0x7352C4


async def send_log_as_discord_webhook(message: str, discord_channel: str) -> None:
    """Log a message to the provided discord channel, if configured."""

    discord_webhook_url = DISCORD_CHANNELS.get(discord_channel)
    if discord_webhook_url is None:
        logger.error(
            "Attempted to send webhook to an unknown discord channel",
            extra={"discord_channel": discord_channel},
        )
        return
    elif discord_webhook_url == "":
        logger.warning(
            "No discord webhook embed is configurated for discord channel",
            extra={"discord_channel": discord_channel},
        )
        return

    embed = Webhook(discord_webhook_url, color=DISCORD_WEBHOOK_EMBED_COLOR)
    embed.set_author(
        name="",
        icon="",
    )
    embed.add_field(name="New moderation action logged! :tools:", value=message)
    embed.set_footer(text="bancho-service ⚓")

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


async def send_log(
    user_id: int,
    message: str,
    discord_channel: str | None = None,
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
        job_scheduling.schedule_job(
            send_log_as_discord_webhook(
                message=f"{user_utils.get_username_from_id(user_id)} {message}",
                discord_channel=discord_channel,
            ),
        )
