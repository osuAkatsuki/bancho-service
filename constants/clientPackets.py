from __future__ import annotations

from constants import dataTypes
from constants import slotStatuses
from helpers import packetHelper

""" Protocol v20 """


def changeProtocolVersion(stream):
    return packetHelper.readPacketData(stream, (("version", dataTypes.UINT32),))["data"]


""" Protocol v19 """

ACTION_CHANGE_FMT = (
    ("actionID", dataTypes.BYTE),
    ("actionText", dataTypes.STRING),
    ("actionMd5", dataTypes.STRING),
    ("actionMods", dataTypes.UINT32),
    ("gameMode", dataTypes.BYTE),
    ("beatmapID", dataTypes.SINT32),
)
""" Users listing packets """


def userActionChange(stream):
    return packetHelper.readPacketData(stream, ACTION_CHANGE_FMT)["data"]


def userStatsRequest(stream):
    return packetHelper.readPacketData(stream, (("users", dataTypes.INT_LIST),))["data"]


def userPanelRequest(stream):
    return packetHelper.readPacketData(stream, (("users", dataTypes.INT_LIST),))["data"]


""" Client chat packets """
PUBLIC_MSG_FMT = (
    ("unknown", dataTypes.STRING),
    ("message", dataTypes.STRING),
    ("to", dataTypes.STRING),
)


def sendPublicMessage(stream):
    return packetHelper.readPacketData(stream, PUBLIC_MSG_FMT)["data"]


PRIVATE_MSG_FMT = (
    ("unknown", dataTypes.STRING),
    ("message", dataTypes.STRING),
    ("to", dataTypes.STRING),
    ("unknown2", dataTypes.UINT32),
)


def sendPrivateMessage(stream):
    return packetHelper.readPacketData(stream, PRIVATE_MSG_FMT)["data"]


def setAwayMessage(stream):
    return packetHelper.readPacketData(
        stream,
        (("unknown", dataTypes.STRING), ("awayMessage", dataTypes.STRING)),
    )["data"]


def blockDM(stream):
    return packetHelper.readPacketData(stream, (("value", dataTypes.UINT32),))["data"]


def channelJoin(stream):
    return packetHelper.readPacketData(stream, (("channel", dataTypes.STRING),))["data"]


def channelPart(stream):
    return packetHelper.readPacketData(stream, (("channel", dataTypes.STRING),))["data"]


def addRemoveFriend(stream):
    return packetHelper.readPacketData(stream, (("friendID", dataTypes.SINT32),))[
        "data"
    ]


""" Spectator packets """


def startSpectating(stream):
    return packetHelper.readPacketData(stream, (("userID", dataTypes.SINT32),))["data"]


""" Multiplayer packets """
MATCH_SETTINGS_FMT_FIRST = (
    ("matchID", dataTypes.UINT16),
    ("inProgress", dataTypes.BYTE),
    ("unknown", dataTypes.BYTE),
    ("mods", dataTypes.UINT32),
    ("matchName", dataTypes.STRING),
    ("matchPassword", dataTypes.STRING),
    ("beatmapName", dataTypes.STRING),
    ("beatmapID", dataTypes.UINT32),
    ("beatmapMD5", dataTypes.STRING),
    *[(f"slot{i}Status", dataTypes.BYTE) for i in range(16)],
    *[(f"slot{i}Team", dataTypes.BYTE) for i in range(16)],
)
MATCH_SETTINGS_FMT_SECOND = (
    ("hostUserID", dataTypes.SINT32),
    ("gameMode", dataTypes.BYTE),
    ("scoringType", dataTypes.BYTE),
    ("teamType", dataTypes.BYTE),
    ("freeMods", dataTypes.BYTE),
)
MATCH_SETTINGS_FMT_THIRD = (*[(f"slot{i}Mods", dataTypes.UINT32) for i in range(16)],)


def matchSettings(stream):
    # Data to return, will be merged later
    data = {}

    # Read first part
    result = packetHelper.readPacketData(stream, MATCH_SETTINGS_FMT_FIRST)
    data.update(result["data"])

    # Next part's start
    start = result["end"]

    # Second part (this one somewhat depends on match state)
    struct: list[tuple[str, int]] = [
        (f"slot{i}ID", dataTypes.SINT32)
        for i in range(16)
        if data[f"slot{i}Status"] not in (slotStatuses.FREE, slotStatuses.LOCKED)
    ]

    # Other settings
    struct.extend(MATCH_SETTINGS_FMT_SECOND)

    # Read second part
    result = packetHelper.readPacketData(stream[start:], tuple(struct), False)
    data.update(result["data"])

    if data["freeMods"] == 0:
        return data

    # Next part's start
    start += result["end"]

    # Read third (final) part
    data.update(
        packetHelper.readPacketData(stream[start:], MATCH_SETTINGS_FMT_THIRD, False)[
            "data"
        ],
    )

    return data


def createMatch(stream):
    return matchSettings(stream)


def changeMatchSettings(stream):
    return matchSettings(stream)


def changeSlot(stream):
    return packetHelper.readPacketData(stream, (("slotID", dataTypes.UINT32),))["data"]


def joinMatch(stream):
    return packetHelper.readPacketData(
        stream,
        (("matchID", dataTypes.UINT32), ("password", dataTypes.STRING)),
    )["data"]


def changeMods(stream):
    return packetHelper.readPacketData(stream, (("mods", dataTypes.UINT32),))["data"]


def lockSlot(stream):
    return packetHelper.readPacketData(stream, (("slotID", dataTypes.UINT32),))["data"]


def transferHost(stream):
    return packetHelper.readPacketData(stream, (("slotID", dataTypes.UINT32),))["data"]


def matchInvite(stream):
    return packetHelper.readPacketData(stream, (("userID", dataTypes.UINT32),))["data"]


MATCH_FRAMES_FMT = (
    ("time", dataTypes.SINT32),
    ("id", dataTypes.BYTE),
    ("count300", dataTypes.UINT16),
    ("count100", dataTypes.UINT16),
    ("count50", dataTypes.UINT16),
    ("countGeki", dataTypes.UINT16),
    ("countKatu", dataTypes.UINT16),
    ("countMiss", dataTypes.UINT16),
    ("totalScore", dataTypes.SINT32),
    ("maxCombo", dataTypes.UINT16),
    ("currentCombo", dataTypes.UINT16),
    ("perfect", dataTypes.BYTE),
    ("currentHp", dataTypes.BYTE),
    ("tagByte", dataTypes.BYTE),
    ("usingScoreV2", dataTypes.BYTE),
)


def matchFrames(stream):
    return packetHelper.readPacketData(stream, MATCH_FRAMES_FMT)["data"]


def tournamentMatchInfoRequest(stream):
    return packetHelper.readPacketData(stream, (("matchID", dataTypes.UINT32),))["data"]


def tournamentJoinMatchChannel(stream):
    return packetHelper.readPacketData(stream, (("matchID", dataTypes.UINT32),))["data"]


def tournamentLeaveMatchChannel(stream):
    return packetHelper.readPacketData(stream, (("matchID", dataTypes.UINT32),))["data"]
