from __future__ import annotations

from os import name
from sys import stdout as _stdout
from typing import Optional
from common.web.discord import Webhook
from requests import RequestException

import settings
from common import generalUtils
from common.constants import bcolors
from common.ripple import userUtils
from objects import glob

ENDL = "\n" if name == "posix" else "\r\n"

MAX_DISCORD_WEBHOOK_RETRIES = 5

def send_discord_webhook(message: str, webhook_url: str) -> None:
    embed = Webhook(webhook_url, color=0x542CB8)
    embed.add_field(name="** **", value=message)
    embed.set_footer(text=f"Akatsuki Anticheat")
    embed.set_thumbnail("https://akatsuki.pw/static/logos/logo.png")

    for _ in range(MAX_DISCORD_WEBHOOK_RETRIES):
        try:
            embed.post()
            break
        except RequestException:
            continue

def logMessage(
    message: str,
    alertType: str = "INFO",
    messageColor: Optional[str] = bcolors.ENDC,
    discord: Optional[str] = None,
    stdout: bool = True,
) -> None:
    """
    Log a message

    :param message: message to log
    :param alertType: alert type string. Can be INFO, WARNING, ERROR or DEBUG. Default: INFO
    :param messageColor: message console ANSI color. Default: no color
    :param discord: If None, don't log to Discord. Default: None
    :param stdout: If True, log to stdout (print). Default: True
    :return:
    """

    # Get type color from alertType
    if alertType == "INFO":
        typeColor = bcolors.CYAN
    elif alertType == "WARNING":
        typeColor = bcolors.YELLOW
    elif alertType == "ERROR":
        typeColor = bcolors.RED
    elif alertType == "CHAT":
        typeColor = bcolors.BLUE
    elif alertType == "DEBUG":
        typeColor = bcolors.PINK
    elif alertType == "ANTICHEAT":
        typeColor = bcolors.PINK
    else:
        typeColor = bcolors.ENDC

    if stdout:
        # send to console, if provided
        console_msg = (
            "{typeColor}[{time}] {type}{endc} - {messageColor}{message}{endc}".format(
                time=generalUtils.getTimestamp(
                    full=False,
                ),  # No need to include date for console
                type=alertType,
                message=message,
                typeColor=typeColor,
                messageColor=messageColor,
                endc=bcolors.ENDC,
            )
        )

        _stdout.write(f"{console_msg}{ENDL}")
        _stdout.flush()

    if discord is not None:
        # send to discord, if provided
        if discord == "ac_general":
            send_discord_webhook(message, settings.WEBHOOK_AC_GENERAL)

        elif discord == "ac_confidential":
            send_discord_webhook(message, settings.WEBHOOK_AC_CONFIDENTIAL)
        else:
            error(f"Unknown discord webhook {discord}")

    # TODO: save to sql?


def warning(message: str, discord: Optional[str] = None) -> None:
    """
    Log a warning to stdout and optionally to Discord

    :param message: warning message
    :param discord: If None, don't log to Discord. Default: None
    :return:
    """
    logMessage(message, "WARNING", bcolors.YELLOW, discord)


def error(message: str, discord: Optional[str] = None) -> None:
    """
    Log a warning message to stdout and optionally to Discord

    :param message: warning message
    :param discord: If None, don't log to Discord. Default: None
    :return:
    """
    logMessage(message, "ERROR", bcolors.RED, discord)


def info(message: str, discord: Optional[str] = None) -> None:
    """
    Log an info message to stdout and optionally to Discord

    :param message: info message
    :param discord: If None, don't log to Discord. Default: None
    :return:
    """
    logMessage(message, "INFO", bcolors.ENDC, discord)


def debug(message: str) -> None:
    """
    Log a debug message to stdout.
    Works only if the server is running in debug mode.

    :param message: debug message
    :return:
    """
    if settings.DEBUG:
        logMessage(message, "DEBUG", bcolors.PINK)


def chat(message: str, discord: Optional[str] = None) -> None:
    """
    Log a public chat message to stdout and to chatlog_public.txt.

    :param message: message content
    :param discord: if True, send the message to discord
    :return:
    """
    logMessage(message, "CHAT", bcolors.BLUE, discord)


def pm(message: str, discord: Optional[str] = None) -> None:
    """
    Log a private chat message to chatlog_private.txt.

    :param message: message content
    :param discord: if True, send the message to discord
    :return:
    """
    logMessage(
        message,
        "CHAT",
        None,
        discord,
        stdout=False,
    )


def ac(message: str, discord: Optional[str] = None) -> None:
    """
    Just a log that is meant to stand out in console. Meant for testing things, generally..

    :param message: message content
    :param discord: if True, send the message to discord
    :return:
    """
    logMessage(message, "ANTICHEAT", bcolors.CYAN, discord)


def rap(
    userID: int,
    message: str,
    discord: Optional[str] = None,
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
    glob.db.execute(
        "INSERT INTO rap_logs (id, userid, text, datetime, through) "  # could be admin in db too?
        "VALUES (NULL, %s, %s, UNIX_TIMESTAMP(), %s)",
        [userID, message, admin],
    )
    logMessage(f"{userUtils.getUsername(userID)} {message}", discord=discord)
