from __future__ import annotations

from os import name
from sys import stdout as _stdout
from typing import Optional

import settings
from common import generalUtils
from common.constants import bcolors
from common.ripple import userUtils
from objects import glob

ENDL = "\n" if name == "posix" else "\r\n"


def logMessage(
    message: str,
    alertType: str = "INFO",
    messageColor: Optional[str] = bcolors.ENDC,
    discord: Optional[str] = None,
    out_file: Optional[str] = None,
    stdout: bool = True,
) -> None:
    """
    Log a message

    :param message: message to log
    :param alertType: alert type string. Can be INFO, WARNING, ERROR or DEBUG. Default: INFO
    :param messageColor: message console ANSI color. Default: no color
    :param discord: Discord channel acronym for Schiavo. If None, don't log to Discord. Default: None
    :param of:	Output file name (inside .data folder). If None, don't log to file. Default: None
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
            glob.schiavo.sendACGeneral(message)
        elif discord == "ac_confidential":
            glob.schiavo.sendACConfidential(message)
        else:
            error(f"Unknown discord webhook {discord}")

    if out_file is not None:
        # send to file, if provided
        file_msg = f"[{generalUtils.getTimestamp(full=True)}] {alertType} - {message}"
        glob.fileBuffers.write(f".data/{out_file}", f"{file_msg}{ENDL}")


def warning(message: str, discord: Optional[str] = None) -> None:
    """
    Log a warning to stdout and optionally to Discord

    :param message: warning message
    :param discord: Discord channel acronym for Schiavo. If None, don't log to Discord. Default: None
    :return:
    """
    logMessage(message, "WARNING", bcolors.YELLOW, discord)


def error(message: str, discord: Optional[str] = None) -> None:
    """
    Log a warning message to stdout and optionally to Discord

    :param message: warning message
    :param discord: Discord channel acronym for Schiavo. If None, don't log to Discord. Default: None
    :return:
    """
    logMessage(message, "ERROR", bcolors.RED, discord)


def info(message: str, discord: Optional[str] = None) -> None:
    """
    Log an info message to stdout and optionally to Discord

    :param message: info message
    :param discord: Discord channel acronym for Schiavo. If None, don't log to Discord. Default: None
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
    logMessage(message, "CHAT", bcolors.BLUE, discord, out_file="chatlog_public.txt")


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
        out_file="chatlog_private.txt",
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
