from __future__ import annotations

from math import floor
from os import _exit
from os import getloadavg
from os import getpid
from os import kill
from os import name
from signal import SIGKILL
from threading import Timer
from time import time
from typing import Any
from typing import NoReturn

import psutil

from common.constants import bcolors
from common.log import logUtils as log
from constants import serverPackets
from helpers import consoleHelper
from objects import glob
from objects import match
from objects import osuToken
from objects import streamList


def runningUnderUnix() -> bool:
    """
    Get if the server is running under UNIX or NT

    :return: True if running under UNIX, otherwise False
    """
    return name == "posix"


def scheduleShutdown(
    sendRestartTime: int,
    restart: bool,
    message: str = "",
    delay: int = 5,
) -> None:
    """
    Schedule a server shutdown/restart

    :param sendRestartTime: time (seconds) to wait before sending server restart packets to every client
    :param restart: if True, server will restart. if False, server will shudown
    :param message: if set, send that message to every client to warn about the shutdown/restart
    :param delay: additional restart delay in seconds. Default: 5
    :return:
    """
    # Console output
    log.info(
        f"bancho-service will {'restart' if restart else 'shutdown'} in {sendRestartTime + delay} seconds!",
    )
    log.info(f"Sending server restart packets in {sendRestartTime} seconds...")

    # Send notification if set
    if message:
        streamList.broadcast("main", serverPackets.notification(message))

    # Schedule server restart packet
    Timer(
        sendRestartTime,
        streamList.broadcast,
        ["main", serverPackets.banchoRestart(delay * 2 * 1000)],
    ).start()
    glob.restarting = True

    # Schedule actual server shutdown/restart some seconds after server restart packet, so everyone gets it
    action = restartServer if restart else shutdownServer
    Timer(sendRestartTime + delay, action).start()


def restartServer() -> NoReturn:
    """
    Restart bancho-service

    :return:
    """
    log.info("Restarting bancho-service...")
    dispose()

    # TODO: publish to redis to restart and update lets
    _exit(0)  # restart handled by script now


def shutdownServer() -> NoReturn:  # type: ignore
    """
    Shutdown bancho-service

    :return:
    """
    log.info("Shutting down bancho-service...")
    dispose()
    sig = SIGKILL  # if runningUnderUnix() else CTRL_C_EVENT
    kill(getpid(), sig)


def getSystemInfo() -> dict[str, Any]:
    """
    Get a dictionary with some system/server info

    :return: ["unix", "connectedUsers", "webServer", "cpuUsage", "totalMemory", "usedMemory", "loadAverage"]
    """
    data = {
        "unix": runningUnderUnix(),
        "connectedUsers": len(osuToken.get_token_ids()),
        "matches": len(match.get_match_ids()),
    }

    # General stats
    delta = time() - glob.startTime
    days = floor(delta / 86400)
    delta -= days * 86400

    hours = floor(delta / 3600)
    delta -= hours * 3600

    minutes = floor(delta / 60)
    delta -= minutes * 60

    seconds = floor(delta)

    data["uptime"] = f"{days}d {hours}h {minutes}m {seconds}s"
    data["cpuUsage"] = psutil.cpu_percent()
    memory = psutil.virtual_memory()
    data["totalMemory"] = f"{memory.total / (1024 ** 3):.2f}"
    data["usedMemory"] = f"{memory.active / (1024 ** 3):.2f}"

    # Unix only stats
    if data["unix"]:
        data["loadAverage"] = getloadavg()
    else:
        data["loadAverage"] = (0, 0, 0)

    return data
