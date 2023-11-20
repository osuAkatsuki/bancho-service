from __future__ import annotations

import asyncio
import gzip
import logging
import random
import struct
from uuid import UUID

import settings
from common.web.requestsManager import AsyncRequestHandler
from constants import exceptions
from constants import packetIDs
from constants import serverPackets
from events import cantSpectateEvent
from events import changeActionEvent
from events import changeMatchModsEvent
from events import changeMatchPasswordEvent
from events import changeMatchSettingsEvent
from events import changeProtocolVersionEvent
from events import changeSlotEvent
from events import channelJoinEvent
from events import channelPartEvent
from events import createMatchEvent
from events import friendAddEvent
from events import friendRemoveEvent
from events import joinLobbyEvent
from events import joinMatchEvent
from events import loginEvent
from events import logoutEvent
from events import matchChangeTeamEvent
from events import matchCompleteEvent
from events import matchFailedEvent
from events import matchFramesEvent
from events import matchHasBeatmapEvent
from events import matchInviteEvent
from events import matchLockEvent
from events import matchNoBeatmapEvent
from events import matchPlayerLoadEvent
from events import matchReadyEvent
from events import matchSkipEvent
from events import matchStartEvent
from events import matchTransferHostEvent
from events import partLobbyEvent
from events import partMatchEvent
from events import requestStatusUpdateEvent
from events import sendPrivateMessageEvent
from events import sendPublicMessageEvent
from events import setAwayMessageEvent
from events import setBlockingDMsEvent
from events import spectateFramesEvent
from events import startSpectatingEvent
from events import stopSpectatingEvent
from events import tournamentJoinMatchChannelEvent
from events import tournamentLeaveMatchChannelEvent
from events import tournamentMatchInfoRequestEvent
from events import userPanelRequestEvent
from events import userStatsRequestEvent
from objects import osuToken
from objects import tokenList
from objects.redisLock import redisLock

PACKET_PROTO = struct.Struct("<HxI")

# Packet map of all bancho related
# interactions with the osu! client.
bancho_packets = {
    packetIDs.client_changeAction: changeActionEvent.handle,
    packetIDs.client_logout: logoutEvent.handle,
    packetIDs.client_friendAdd: friendAddEvent.handle,
    packetIDs.client_friendRemove: friendRemoveEvent.handle,
    packetIDs.client_userStatsRequest: userStatsRequestEvent.handle,
    packetIDs.client_requestStatusUpdate: requestStatusUpdateEvent.handle,
    packetIDs.client_userPanelRequest: userPanelRequestEvent.handle,
    packetIDs.client_channelJoin: channelJoinEvent.handle,
    packetIDs.client_channelPart: channelPartEvent.handle,
    packetIDs.client_sendPublicMessage: sendPublicMessageEvent.handle,
    packetIDs.client_sendPrivateMessage: sendPrivateMessageEvent.handle,
    packetIDs.client_setAwayMessage: setAwayMessageEvent.handle,
    packetIDs.client_userBlockNonFriendsDM: setBlockingDMsEvent.handle,
    packetIDs.client_startSpectating: startSpectatingEvent.handle,
    packetIDs.client_stopSpectating: stopSpectatingEvent.handle,
    packetIDs.client_cantSpectate: cantSpectateEvent.handle,
    packetIDs.client_spectateFrames: spectateFramesEvent.handle,
    packetIDs.client_joinLobby: joinLobbyEvent.handle,
    packetIDs.client_partLobby: partLobbyEvent.handle,
    packetIDs.client_createMatch: createMatchEvent.handle,
    packetIDs.client_joinMatch: joinMatchEvent.handle,
    packetIDs.client_partMatch: partMatchEvent.handle,
    packetIDs.client_matchChangeSlot: changeSlotEvent.handle,
    packetIDs.client_matchChangeSettings: changeMatchSettingsEvent.handle,
    packetIDs.client_matchChangePassword: changeMatchPasswordEvent.handle,
    packetIDs.client_matchChangeMods: changeMatchModsEvent.handle,
    packetIDs.client_matchReady: matchReadyEvent.handle,
    packetIDs.client_matchNotReady: matchReadyEvent.handle,
    packetIDs.client_matchLock: matchLockEvent.handle,
    packetIDs.client_matchStart: matchStartEvent.handle,
    packetIDs.client_matchLoadComplete: matchPlayerLoadEvent.handle,
    packetIDs.client_matchSkipRequest: matchSkipEvent.handle,
    packetIDs.client_matchScoreUpdate: matchFramesEvent.handle,
    packetIDs.client_matchComplete: matchCompleteEvent.handle,
    packetIDs.client_matchNoBeatmap: matchNoBeatmapEvent.handle,
    packetIDs.client_matchHasBeatmap: matchHasBeatmapEvent.handle,
    packetIDs.client_matchTransferHost: matchTransferHostEvent.handle,
    packetIDs.client_matchFailed: matchFailedEvent.handle,
    packetIDs.client_matchChangeTeam: matchChangeTeamEvent.handle,
    packetIDs.client_invite: matchInviteEvent.handle,
    packetIDs.client_tournamentMatchInfoRequest: tournamentMatchInfoRequestEvent.handle,
    packetIDs.client_tournamentJoinMatchChannel: tournamentJoinMatchChannelEvent.handle,
    packetIDs.client_tournamentLeaveMatchChannel: tournamentLeaveMatchChannelEvent.handle,
    packetIDs.client_changeProtocolVersion: changeProtocolVersionEvent.handle,
}

# Packets processed if in restricted mode.
# All other packets will be ignored if the user is in restricted mode
restricted_packets = {
    packetIDs.client_logout,
    packetIDs.client_userStatsRequest,
    packetIDs.client_requestStatusUpdate,
    packetIDs.client_userPanelRequest,
    packetIDs.client_changeAction,
    packetIDs.client_channelJoin,
    packetIDs.client_channelPart,
    packetIDs.client_changeProtocolVersion,
}

HTML_PAGE = (
    "<html><head><title>Welcome to Akatsuki!</title><style type='text/css'>body{width:30%;background:#222;color:#fff;}</style></head><body><pre>"
    "      _/_/    _/                    _/                          _/        _/   <br>"
    "   _/    _/  _/  _/      _/_/_/  _/_/_/_/    _/_/_/  _/    _/  _/  _/          <br>"
    "  _/_/_/_/  _/_/      _/    _/    _/      _/_/      _/    _/  _/_/      _/     <br>"
    " _/    _/  _/  _/    _/    _/    _/          _/_/  _/    _/  _/  _/    _/      <br>"
    "_/    _/  _/    _/    _/_/_/      _/_/  _/_/_/      _/_/_/  _/    _/  _/       <br>"
    "<b>Click circle.. circle no click?</b><br><br>"
    "<marquee style='white-space:pre;'><br>"
    "                          .. o  .<br>"
    "                         o.o o . o<br>"
    "                        oo...<br>"
    "                    __[]__<br>"
    "    cmyui--> _\\:D/_/o_o_o_|__     <span style=\"font-family: 'Comic Sans MS'; font-size: 8pt;\">u wot m8</span><br>"
    '             \\""""""""""""""/<br>'
    "              \\ . ..  .. . /<br>"
    "^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^<br>"
    "</marquee><br><strike>Serving one handed osu! gamers since the dawn of time<i>&copy; Ripple & Akatsuki, 2020</i></pre></body></html>"
)


class handler(AsyncRequestHandler):
    async def _post(self) -> None:
        # Client's token string and request data
        requestTokenString = self.request.headers.get("osu-token")
        requestData = self.request.body

        # XXX: temporarily doing some performance monitoring
        if random.randint(0, 20) == 20:
            tasks = asyncio.all_tasks()
            logging.info(
                "Concurrent tasks report",
                extra={"concurrent_tasks_count": len(tasks)},
            )
            if len(tasks) > 100:
                logging.warning(
                    "Too many concurrent tasks",
                    extra={"concurrent_tasks": [x.get_name() for x in tasks]},
                )

        # Server's token string and request data
        responseTokenString = "ayy"
        responseData = b""

        if requestTokenString is None:
            # No token, first request. Handle login.
            responseTokenString, responseData = await loginEvent.handle(self)
        else:
            # Make sure token is valid syntax
            try:
                UUID(requestTokenString)
            except ValueError:
                # Invalid token, ignore request
                self.set_status(400)
                self.write(b"Invalid token")
                return

            userToken = None  # default value
            token_processing_lock = None
            try:
                # This is not the first packet, send response based on client's request
                # Packet start position, used to read stacked packets
                pos = 0

                # Lock token to prevent multiple requests from being processed at once
                # token_processing_lock = redisLock(
                #     f"{osuToken.make_key(requestTokenString)}:processing_lock",
                # )
                # await token_processing_lock.acquire()

                # Make sure the token exists
                userToken = await osuToken.get_token(requestTokenString)
                if userToken is None:
                    raise exceptions.tokenNotFoundException()

                # Keep reading packets until everything has been read
                requestDataLen = len(requestData)
                while pos < requestDataLen:
                    # Get packet from stack starting from new packet
                    leftData = requestData[pos:]

                    # Get packet ID, data length and data
                    packetID, dataLength = PACKET_PROTO.unpack(leftData[:7])
                    packetData = leftData[: dataLength + 7]

                    # Process/ignore packet
                    if packetID != 4:
                        if packetID in bancho_packets:
                            if (
                                not osuToken.is_restricted(userToken["privileges"])
                                or packetID in restricted_packets
                            ):
                                await bancho_packets[packetID](userToken, packetData)
                        # else:
                        # 	#log.warning(f"Unhandled: {packetID}")
                    else:
                        # This is a ping packet (4) - update ping time for timeout
                        await osuToken.updatePingTime(userToken["token_id"])

                    # Update pos so we can read the next stacked packet
                    # +7 because we add packet ID bytes, unused byte and data length bytes
                    pos += dataLength + 7

                # Token queue built, send it
                responseTokenString = userToken["token_id"]
                responseData = await osuToken.dequeue(userToken["token_id"])

            except exceptions.tokenNotFoundException:
                # Client thinks it's logged in when it's
                # not; we probably restarted the server.
                responseData = serverPackets.notification(
                    "Server has restarted.",
                ) + serverPackets.banchoRestart(0)
            finally:
                if userToken is not None:
                    # Packet handlers may have updated session information, or may have
                    # deleted the session (e.g. logout packet). Re-fetch it to ensure
                    # we have the latest state in-memory
                    userToken = await osuToken.get_token(requestTokenString)
                    if userToken is not None:
                        # Delete token if kicked
                        if userToken["kicked"]:
                            await tokenList.deleteToken(userToken["token_id"])

                # Release processing lock
                # if token_processing_lock is not None:
                #     await token_processing_lock.release()

        # Send server's response to client
        # We don't use token object because we might not have a token (failed login)
        if settings.APP_GZIP:
            # First, write the gzipped response
            self.write(gzip.compress(responseData, settings.APP_GZIP_LEVEL))

            # Then, add gzip headers
            self.add_header("Vary", "Accept-Encoding")
            self.add_header("Content-Encoding", "gzip")
        else:
            # First, write the response
            self.write(responseData)

        # Add all the headers AFTER the response has been written
        self.set_status(200)
        self.add_header("cho-token", responseTokenString)
        # self.add_header("cho-protocol", "19")
        # self.add_header("Connection", "keep-alive")
        # self.add_header("Keep-Alive", "timeout=5, max=100")
        self.add_header("Content-Type", "text/html; charset=UTF-8")

    async def post(self) -> None:
        # XXX:HACK around tornado/asyncio poor exception support
        try:
            await self._post()
        except Exception:
            logging.exception("An unhandled error occurred")

    async def get(self) -> None:
        self.write(HTML_PAGE)
