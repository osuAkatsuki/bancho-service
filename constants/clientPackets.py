from __future__ import annotations

from constants import slotStatuses
from constants.dataTypes import DataTypes
from helpers import packetHelper

""" Protocol v20 """


def changeProtocolVersion(stream):
    return packetHelper.readPacketData(stream, (("version", DataTypes.UINT32),))["data"]


""" Protocol v19 """

ACTION_CHANGE_FMT = (
    ("actionID", DataTypes.BYTE),
    ("actionText", DataTypes.STRING),
    ("actionMd5", DataTypes.STRING),
    ("actionMods", DataTypes.UINT32),
    ("gameMode", DataTypes.BYTE),
    ("beatmapID", DataTypes.SINT32),
)
""" Users listing packets """


def userActionChange(stream):
    return packetHelper.readPacketData(stream, ACTION_CHANGE_FMT)["data"]


def userStatsRequest(stream):
    return packetHelper.readPacketData(stream, (("users", DataTypes.INT_LIST),))["data"]


def userPanelRequest(stream):
    return packetHelper.readPacketData(stream, (("users", DataTypes.INT_LIST),))["data"]


""" Client chat packets """
PUBLIC_MSG_FMT = (
    ("unknown", DataTypes.STRING),
    ("message", DataTypes.STRING),
    ("to", DataTypes.STRING),
)


def sendPublicMessage(stream):
    return packetHelper.readPacketData(stream, PUBLIC_MSG_FMT)["data"]


PRIVATE_MSG_FMT = (
    ("unknown", DataTypes.STRING),
    ("message", DataTypes.STRING),
    ("to", DataTypes.STRING),
    ("unknown2", DataTypes.UINT32),
)


def sendPrivateMessage(stream):
    return packetHelper.readPacketData(stream, PRIVATE_MSG_FMT)["data"]


def setAwayMessage(stream):
    return packetHelper.readPacketData(
        stream,
        (("unknown", DataTypes.STRING), ("awayMessage", DataTypes.STRING)),
    )["data"]


def blockDM(stream):
    return packetHelper.readPacketData(stream, (("value", DataTypes.UINT32),))["data"]


def channelJoin(stream):
    return packetHelper.readPacketData(stream, (("channel", DataTypes.STRING),))["data"]


def channelPart(stream):
    return packetHelper.readPacketData(stream, (("channel", DataTypes.STRING),))["data"]


def addRemoveFriend(stream):
    return packetHelper.readPacketData(stream, (("friendID", DataTypes.SINT32),))[
        "data"
    ]


""" Spectator packets """


def startSpectating(stream):
    return packetHelper.readPacketData(stream, (("userID", DataTypes.SINT32),))["data"]


""" Multiplayer packets """
MATCH_SETTINGS_FMT_FIRST = (
    ("matchID", DataTypes.UINT16),
    ("inProgress", DataTypes.BYTE),
    ("unknown", DataTypes.BYTE),
    ("mods", DataTypes.UINT32),
    ("matchName", DataTypes.STRING),
    ("matchPassword", DataTypes.STRING),
    ("beatmapName", DataTypes.STRING),
    ("beatmapID", DataTypes.UINT32),
    ("beatmapMD5", DataTypes.STRING),
    *[(f"slot{i}Status", DataTypes.BYTE) for i in range(16)],
    *[(f"slot{i}Team", DataTypes.BYTE) for i in range(16)],
)
MATCH_SETTINGS_FMT_SECOND = (
    ("hostUserID", DataTypes.SINT32),
    ("gameMode", DataTypes.BYTE),
    ("scoringType", DataTypes.BYTE),
    ("teamType", DataTypes.BYTE),
    ("freeMods", DataTypes.BYTE),
)
MATCH_SETTINGS_FMT_THIRD = (*[(f"slot{i}Mods", DataTypes.UINT32) for i in range(16)],)


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
        (f"slot{i}ID", DataTypes.SINT32)
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
    return packetHelper.readPacketData(stream, (("slotID", DataTypes.UINT32),))["data"]


def joinMatch(stream):
    return packetHelper.readPacketData(
        stream,
        (("matchID", DataTypes.UINT32), ("password", DataTypes.STRING)),
    )["data"]


def changeMods(stream):
    return packetHelper.readPacketData(stream, (("mods", DataTypes.UINT32),))["data"]


def lockSlot(stream):
    return packetHelper.readPacketData(stream, (("slotID", DataTypes.UINT32),))["data"]


def transferHost(stream):
    return packetHelper.readPacketData(stream, (("slotID", DataTypes.UINT32),))["data"]


def matchInvite(stream):
    return packetHelper.readPacketData(stream, (("userID", DataTypes.UINT32),))["data"]


MATCH_FRAMES_FMT = (
    ("time", DataTypes.SINT32),
    ("id", DataTypes.BYTE),
    ("count300", DataTypes.UINT16),
    ("count100", DataTypes.UINT16),
    ("count50", DataTypes.UINT16),
    ("countGeki", DataTypes.UINT16),
    ("countKatu", DataTypes.UINT16),
    ("countMiss", DataTypes.UINT16),
    ("totalScore", DataTypes.SINT32),
    ("maxCombo", DataTypes.UINT16),
    ("currentCombo", DataTypes.UINT16),
    ("perfect", DataTypes.BYTE),
    ("currentHp", DataTypes.BYTE),
    ("tagByte", DataTypes.BYTE),
    ("usingScoreV2", DataTypes.BYTE),
)


def matchFrames(stream):
    return packetHelper.readPacketData(stream, MATCH_FRAMES_FMT)["data"]


def tournamentMatchInfoRequest(stream):
    return packetHelper.readPacketData(stream, (("matchID", DataTypes.UINT32),))["data"]


def tournamentJoinMatchChannel(stream):
    return packetHelper.readPacketData(stream, (("matchID", DataTypes.UINT32),))["data"]


def tournamentLeaveMatchChannel(stream):
    return packetHelper.readPacketData(stream, (("matchID", DataTypes.UINT32),))["data"]
