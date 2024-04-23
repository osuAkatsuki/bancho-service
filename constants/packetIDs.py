"""Contain server and client packet IDs"""
from __future__ import annotations

client_changeAction = 0
client_sendPublicMessage = 1
client_logout = 2
client_requestStatusUpdate = 3
server_userID = 5
server_sendMessage = 7
server_userStats = 11
server_userLogout = 12
server_spectatorJoined = 13
server_spectatorLeft = 14
server_spectateFrames = 15
client_startSpectating = 16
client_stopSpectating = 17
client_spectateFrames = 18
client_cantSpectate = 21
server_spectatorCantSpectate = 22
server_getAttention = 23
server_notification = 24
client_sendPrivateMessage = 25
server_updateMatch = 26
server_newMatch = 27
server_disposeMatch = 28
client_partLobby = 29
client_joinLobby = 30
client_createMatch = 31
client_joinMatch = 32
client_partMatch = 33
server_matchJoinSuccess = 36
server_matchJoinFail = 37
client_matchChangeSlot = 38
client_matchReady = 39
client_matchLock = 40
client_matchChangeSettings = 41
server_fellowSpectatorJoined = 42
server_fellowSpectatorLeft = 43
client_matchStart = 44
server_matchStart = 46
client_matchScoreUpdate = 47
server_matchScoreUpdate = 48
client_matchComplete = 49
server_matchTransferHost = 50
client_matchChangeMods = 51
client_matchLoadComplete = 52
server_matchAllPlayersLoaded = 53
client_matchNoBeatmap = 54
client_matchNotReady = 55
client_matchFailed = 56
server_matchPlayerFailed = 57
server_matchComplete = 58
client_matchHasBeatmap = 59
client_matchSkipRequest = 60
server_matchSkip = 61
client_channelJoin = 63
server_channelJoinSuccess = 64
server_channelInfo = 65
server_channelKicked = 66
client_beatmapInfoRequest = 68
server_beatmapInfoReply = 69
client_matchTransferHost = 70
server_supporterGMT = 71
server_friendsList = 72
client_friendAdd = 73
client_friendRemove = 74
server_protocolVersion = 75
server_mainMenuIcon = 76
client_matchChangeTeam = 77
client_channelPart = 78
client_recieveUpdates = 79
server_takeScreenshot = 80
server_matchPlayerSkipped = 81
client_setAwayMessage = 82
server_userPanel = 83
client_userStatsRequest = 85
server_restart = 86
client_invite = 87
server_invite = 88
server_channelInfoEnd = 89
client_matchChangePassword = 90
server_matchChangePassword = 91
server_silenceEnd = 92
client_tournamentMatchInfoRequest = 93
server_userSilenced = 94
server_userPresenceBundle = 96
client_userPanelRequest = 97
client_userBlockNonFriendsDM = 99
server_targetBlockingNonFriendsDM = 100
server_targetSilenced = 101
server_sendRTX = 105
server_matchAbort = 106
server_switchServer = 107
client_tournamentJoinMatchChannel = 108
client_tournamentLeaveMatchChannel = 109

# custom
client_changeProtocolVersion = 110


def get_packet_name(packet_id: int) -> str:
    """
    Get the name of a packet by its ID

    :param packet_id: ID of the packet
    :return: Name of the packet
    """
    return {
        client_changeAction: "client_changeAction",
        client_sendPublicMessage: "client_sendPublicMessage",
        client_logout: "client_logout",
        client_requestStatusUpdate: "client_requestStatusUpdate",
        server_userID: "server_userID",
        server_sendMessage: "server_sendMessage",
        server_userStats: "server_userStats",
        server_userLogout: "server_userLogout",
        server_spectatorJoined: "server_spectatorJoined",
        server_spectatorLeft: "server_spectatorLeft",
        server_spectateFrames: "server_spectateFrames",
        client_startSpectating: "client_startSpectating",
        client_stopSpectating: "client_stopSpectating",
        client_spectateFrames: "client_spectateFrames",
        client_cantSpectate: "client_cantSpectate",
        server_spectatorCantSpectate: "server_spectatorCantSpectate",
        server_getAttention: "server_getAttention",
        server_notification: "server_notification",
        client_sendPrivateMessage: "client_sendPrivateMessage",
        server_updateMatch: "server_updateMatch",
        server_newMatch: "server_newMatch",
        server_disposeMatch: "server_disposeMatch",
        client_partLobby: "client_partLobby",
        client_joinLobby: "client_joinLobby",
        client_createMatch: "client_createMatch",
        client_joinMatch: "client_joinMatch",
        client_partMatch: "client_partMatch",
        server_matchJoinSuccess: "server_matchJoinSuccess",
        server_matchJoinFail: "server_matchJoinFail",
        client_matchChangeSlot: "client_matchChangeSlot",
        client_matchReady: "client_matchReady",
        client_matchLock: "client_matchLock",
        client_matchChangeSettings: "client_matchChangeSettings",
        server_fellowSpectatorJoined: "server_fellowSpectatorJoined",
        server_fellowSpectatorLeft: "server_fellowSpectatorLeft",
        client_matchStart: "client_matchStart",
        server_matchStart: "server_matchStart",
        client_matchScoreUpdate: "client_matchScoreUpdate",
        server_matchScoreUpdate: "server_matchScoreUpdate",
        client_matchComplete: "client_matchComplete",
        server_matchTransferHost: "server_matchTransferHost",
        client_matchChangeMods: "client_matchChangeMods",
        client_matchLoadComplete: "client_matchLoadComplete",
        server_matchAllPlayersLoaded: "server_matchAllPlayersLoaded",
        client_matchNoBeatmap: "client_matchNoBeatmap",
        client_matchNotReady: "client_matchNotReady",
        client_matchFailed: "client_matchFailed",
        server_matchPlayerFailed: "server_matchPlayerFailed",
        server_matchComplete: "server_matchComplete",
        client_matchHasBeatmap: "client_matchHasBeatmap",
        client_matchSkipRequest: "client_matchSkipRequest",
        server_matchSkip: "server_matchSkip",
        client_channelJoin: "client_channelJoin",
        server_channelJoinSuccess: "server_channelJoinSuccess",
        server_channelInfo: "server_channelInfo",
        server_channelKicked: "server_channelKicked",
        client_beatmapInfoRequest: "client_beatmapInfoRequest",
        server_beatmapInfoReply: "server_beatmapInfoReply",
        client_matchTransferHost: "client_matchTransferHost",
        server_supporterGMT: "server_supporterGMT",
        server_friendsList: "server_friendsList",
        client_friendAdd: "client_friendAdd",
        client_friendRemove: "client_friendRemove",
        server_protocolVersion: "server_protocolVersion",
        server_mainMenuIcon: "server_mainMenuIcon",
        client_matchChangeTeam: "client_matchChangeTeam",
        client_channelPart: "client_channelPart",
        client_recieveUpdates: "client_recieveUpdates",
        server_takeScreenshot: "server_takeScreenshot",
        server_matchPlayerSkipped: "server_matchPlayerSkipped",
        client_setAwayMessage: "client_setAwayMessage",
        server_userPanel: "server_userPanel",
        client_userStatsRequest: "client_userStatsRequest",
        server_restart: "server_restart",
        client_invite: "client_invite",
        server_invite: "server_invite",
        server_channelInfoEnd: "server_channelInfoEnd",
        client_matchChangePassword: "client_matchChangePassword",
        server_matchChangePassword: "server_matchChangePassword",
        server_silenceEnd: "server_silenceEnd",
        client_tournamentMatchInfoRequest: "client_tournamentMatchInfoRequest",
        server_userSilenced: "server_userSilenced",
        server_userPresenceBundle: "server_userPresenceBundle",
        client_userPanelRequest: "client_userPanelRequest",
        client_userBlockNonFriendsDM: "client_userBlockNonFriendsDM",
        server_targetBlockingNonFriendsDM: "server_targetBlockingNonFriendsDM",
        server_targetSilenced: "server_targetSilenced",
        server_sendRTX: "server_sendRTX",
        server_matchAbort: "server_matchAbort",
        server_switchServer: "server_switchServer",
        client_tournamentJoinMatchChannel: "client_tournamentJoinMatchChannel",
        client_tournamentLeaveMatchChannel: "client_tournamentLeaveMatchChannel",
        client_changeProtocolVersion: "client_changeProtocolVersion",
    }.get(packet_id, "Unknown packet ID")
