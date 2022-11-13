from __future__ import annotations

from common.constants import bcolors
from objects import glob


def printServerStartHeader(asciiArt: bool = True) -> None:
    """
    Print server start message

    :param asciiArt: print BanchoBoat ascii art. Default: True
    :return:
    """
    if asciiArt:
        print(
            bcolors.GREEN,
            "      _/_/    _/                    _/                          _/        _/",
            "   _/    _/  _/  _/      _/_/_/  _/_/_/_/    _/_/_/  _/    _/  _/  _/",
            "  _/_/_/_/  _/_/      _/    _/    _/      _/_/      _/    _/  _/_/      _/",
            " _/    _/  _/  _/    _/    _/    _/          _/_/  _/    _/  _/  _/    _/",
            "_/    _/  _/    _/    _/_/_/      _/_/  _/_/_/      _/_/_/  _/    _/  _/",
            bcolors.ENDC,
            sep="\n",
        )

    printColored(
        f"> Welcome to pep.py osu!bancho server v{glob.VERSION}",
        bcolors.GREEN,
    )
    printColored("> Made by the Ripple and Akatsuki teams", bcolors.GREEN)
    printColored(
        f"> {bcolors.UNDERLINE}https://github.com/osuAkatsuki/pep.py",
        bcolors.GREEN,
    )
    printColored("> Press CTRL+C to exit\n", bcolors.GREEN)


def printNoNl(string: str) -> None:
    """
    Print a string without \n at the end

    :param string: string to print
    :return:
    """
    print(string, end="")


def printColored(string: str, color: str) -> None:
    """
    Print a colored string

    :param string: string to print
    :param color: ANSI color code
    :return:
    """
    print(f"{color}{string}{bcolors.ENDC}")


def printError() -> None:
    """
    Print a red "Error"

    :return:
    """
    printColored("Error", bcolors.RED)


def printDone() -> None:
    """
    Print a green "Done"

    :return:
    """
    printColored("Done", bcolors.GREEN)


def printWarning() -> None:
    """
    Print a yellow "Warning"

    :return:
    """
    printColored("Warning", bcolors.YELLOW)
