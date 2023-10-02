from __future__ import annotations

import hashlib
import logging
import re
import time
from datetime import datetime as dt
from datetime import timedelta as td

from amplitude.event import BaseEvent
from amplitude.event import EventOptions
from amplitude.event import Identify

import settings
from common import generalUtils
from common.constants import privileges
from common.log import rap_logs
from common.ripple import userUtils
from common.web.requestsManager import AsyncRequestHandler
from constants import exceptions
from constants import serverPackets
from helpers import chatHelper as chat
from helpers import countryHelper
from helpers import locationHelper
from objects import channelList
from objects import glob
from objects import osuToken
from objects import stream
from objects import streamList
from objects import tokenList
from objects import verifiedCache
from objects.redisLock import redisLock

osu_ver_regex = re.compile(
    r"^b(?P<ver>\d{8})(?:\.(?P<subver>\d))?"
    r"(?P<stream>beta|cuttingedge|dev|tourney)?$",
)


async def handle(web_handler: AsyncRequestHandler) -> tuple[str, bytes]:  # token, data
    # Data to return
    userToken = None
    responseTokenString = "ayy"
    responseData = bytearray()

    # Get client ip of the incoming request
    requestIP = web_handler.getRequestIP()

    # Split POST body so we can get username/password/hardware data
    loginData = web_handler.request.body.decode()[:-1].split("\n")

    try:
        # Make sure loginData is valid
        if len(loginData) < 3:
            raise exceptions.invalidArgumentsException()

        # Get HWID, MAC address and more
        # Structure (new line = "|", already split)
        # [0] osu! version
        # [1] plain mac addresses, separated by "."
        # [2] mac addresses hash set
        # [3] unique ID
        # [4] disk ID
        splitData = loginData[2].split("|")
        osuVersionStr = splitData[0]
        utc_offset = int(splitData[1])
        if len(clientData := splitData[3].split(":")[:5]) < 4:
            raise exceptions.forceUpdateException()
        block_non_friends_dm = splitData[4] == "1"

        # Try to get the ID from username
        username = loginData[0]
        userID = await userUtils.getID(username)

        if not userID:
            # Invalid username
            raise exceptions.loginFailedException()
        elif userID == 999:
            raise exceptions.invalidArgumentsException()

        if not await userUtils.checkLogin(userID, loginData[1]):
            # Invalid password
            raise exceptions.loginFailedException()

        # Make sure we are not banned or locked
        priv = await userUtils.getPrivileges(userID)
        pending_verification = priv & privileges.USER_PENDING_VERIFICATION != 0

        if not pending_verification:
            if not priv & (privileges.USER_PUBLIC | privileges.USER_NORMAL):
                raise exceptions.loginBannedException()
            if (
                priv & privileges.USER_PUBLIC != 0
                and priv & privileges.USER_NORMAL == 0
            ):
                raise exceptions.loginLockedException()

        restricted = priv & privileges.USER_PUBLIC == 0

        if v_argstr in web_handler.request.arguments or osuVersionStr == v_argverstr:
            raise exceptions.haxException()

        if not (rgx := osu_ver_regex.match(osuVersionStr)):
            raise exceptions.loginFailedException()

        osuVersion = dt(
            year=int(rgx["ver"][0:4]),
            month=int(rgx["ver"][4:6]),
            day=int(rgx["ver"][6:8]),
        )

        # disallow clients older than 1 year
        if osuVersion < (dt.now() - td(365)):
            logging.warning(
                "Denied login from client too old",
                extra={"version": osuVersionStr},
            )
            raise exceptions.haxException()

        """ No login errors! """

        # Verify this user (if pending activation)
        firstLogin = False
        shouldBan = False
        if pending_verification or not await userUtils.hasVerifiedHardware(userID):
            if await userUtils.verifyUser(userID, clientData):
                # Valid account
                logging.info(
                    "User verified their account",
                    extra={"user_id": userID, "username": username},
                )
                await verifiedCache.set(userID, True)
                firstLogin = True
            else:
                # Multiaccount detected
                logging.warning(
                    "User tried to create another account",
                    extra={"user_id": userID, "username": username},
                )
                await verifiedCache.set(userID, False)
                shouldBan = True

        # Save HWID in db for multiaccount detection
        hwAllowed = await userUtils.logHardware(userID, clientData, firstLogin)

        # This is false only if HWID is empty
        # if HWID is banned, we get restricted so there's no
        # need to deny bancho access
        if not hwAllowed:
            raise exceptions.haxException()

        # Log user IP
        await userUtils.logIP(userID, requestIP)

        if shouldBan:
            await userUtils.ban(userID)
            raise exceptions.loginBannedException()

        # Delete old tokens for that user and generate a new one
        isTournament = rgx["stream"] == "tourney"

        if clientData[4] == "dcfcd07e645d245babe887e5e2daa016":
            # NOTE: this is the result of `md5(md5("0"))`.
            # The osu! client will send this sometimes because WMI
            # may return a "0" as the disk serial number if a hardware
            # manufacturer has not set one.
            # (disk signature is optional but serial number is required)
            amplitude_device_id = None
        else:
            amplitude_device_id = hashlib.sha1(clientData[4].encode()).hexdigest()

        async with redisLock("bancho:locks:tokens"):
            if not isTournament:
                await tokenList.deleteOldTokens(userID)

            userToken = await tokenList.addToken(
                userID,
                ip=requestIP,
                irc=False,
                utc_offset=utc_offset,
                tournament=isTournament,
                block_non_friends_dm=block_non_friends_dm,
                amplitude_device_id=amplitude_device_id,
            )
            username = userToken["username"]  # trust the one from the db

        responseTokenString = userToken["token_id"]

        # Console output
        logging.info(
            "User logged in",
            extra={
                "user_id": userID,
                "username": username,
                "online_users": len(await osuToken.get_token_ids()),
            },
        )

        # Check restricted mode (and eventually send message)
        await osuToken.checkRestricted(userToken["token_id"])

        """ osu!Akatuki account freezing. """

        # Get the user's `frozen` status from the DB
        # For a normal user, this will return 0.
        # For a frozen user, this will return a unix timestamp (the date of their pending restriction).
        freeze_timestamp = await userUtils.getFreezeTime(userID)
        current_time = int(time.time())

        if freeze_timestamp:
            if freeze_timestamp == 1:  # Begin the timer.
                freeze_timestamp = await userUtils.beginFreezeTimer(userID)

            # reason = await userUtils.getFreezeReason(userID)
            # freeze_str = f" as a result of:\n\n{reason}\n" if reason else ""

            if freeze_timestamp > current_time:  # We are warning the user
                aika_token = await tokenList.getTokenFromUserID(999)
                assert aika_token is not None

                await chat.sendMessage(
                    token_id=aika_token["token_id"],
                    to=username,
                    message="\n".join(
                        [
                            f"Your account has been frozen",  # "Your account has been frozen{freeze_str}"
                            "This is not a restriction, but will lead to one if ignored.",
                            "You are required to submit a liveplay using the (specified criteria)[https://bit.ly/Akatsuki-Liveplay]",
                            "If you have any questions or are ready to liveplay, please open a ticket on our (Discord)[https://akatsuki.gg/discord].",
                            f"Time left until account restriction: {td(seconds = freeze_timestamp - current_time)}.",
                        ],
                    ),
                )

            else:  # We are restricting the user
                # TODO: perhaps move this to the cron?
                # right now a user can avoid a resitrction by simply not logging in lol..
                await userUtils.restrict(userID)
                await userUtils.unfreeze(userID, _log=False)

                await osuToken.enqueue(
                    userToken["token_id"],
                    serverPackets.notification(
                        "\n\n".join(
                            [
                                "Your account has been automatically restricted due to an account freeze being left unhandled for over 7 days.",
                                "You are still welcome to liveplay, although your account will remain in restricted mode unless this is handled.",
                            ],
                        ),
                    ),
                )
                await rap_logs.send_rap_log(
                    userID,
                    "has been automatically restricted due to a pending freeze.",
                )
                await rap_logs.send_rap_log_as_discord_webhook(
                    message=f"[{username}](https://akatsuki.gg/u/{userID}) has been automatically restricted due to a pending freeze.",
                    discord_channel="ac_general",
                )

        # Send message if premium / donor expires soon
        # This should NOT be done at login, but done by the cron
        if userToken["privileges"] & privileges.USER_DONOR:
            expireDate = await userUtils.getDonorExpire(userID)
            premium = userToken["privileges"] & privileges.USER_PREMIUM
            rolename = "premium" if premium else "supporter"

            if current_time >= expireDate:
                await userUtils.setPrivileges(
                    userID,
                    userToken["privileges"] - privileges.USER_DONOR
                    | (privileges.USER_PREMIUM if premium else 0),
                )

                # 36 = supporter, 59 = premium
                badges = await glob.db.fetchAll(
                    "SELECT id FROM user_badges WHERE badge IN (59, 36) AND user = %s",
                    [userID],
                )
                if badges:
                    for (
                        badge
                    ) in badges:  # Iterate through user badges, deleting them all
                        await glob.db.execute(
                            "DELETE FROM user_badges WHERE id = %s",
                            [badge["id"]],
                        )

                # Remove their custom privileges
                await glob.db.execute(
                    "UPDATE users_stats set can_custom_badge = 0, show_custom_badge = 0 WHERE id = %s",
                    [userID],
                )

                await rap_logs.send_rap_log(userID, f"{rolename} subscription expired.")
                await rap_logs.send_rap_log_as_discord_webhook(
                    message=f"[{username}](https://akatsuki.gg/u/{userID})'s {rolename} subscription has expired.",
                    discord_channel="ac_confidential",
                )

                await osuToken.enqueue(
                    userToken["token_id"],
                    serverPackets.notification(
                        "\n\n".join(
                            [
                                f"Your {rolename} tag has expired.",
                                "Whether you continue to support us or not, we'd like to thank you "
                                "to the moon and back for your support so far - it really means everything to us.",
                                "- cmyui, and the Akatsuki Team",
                            ],
                        ),
                    ),
                )

            elif (
                expireDate - current_time <= 86400 * 7
            ):  # Notify within 7 days of expiry
                expireIn = generalUtils.secondsToReadable(expireDate - current_time)
                await osuToken.enqueue(
                    userToken["token_id"],
                    serverPackets.notification(
                        f"Your {rolename} tag expires in {expireIn}.",
                    ),
                )

        # Set silence end UNIX time in token
        await osuToken.update_token(
            userToken["token_id"],
            silence_end_time=await userUtils.getSilenceEnd(userID),
        )

        # Get only silence remaining seconds
        silenceSeconds = await osuToken.getSilenceSecondsLeft(userToken["token_id"])

        # Get supporter/GMT
        userGMT = osuToken.is_staff(userToken["privileges"])
        userTournament = userToken["privileges"] & privileges.USER_TOURNAMENT_STAFF > 0

        # userSupporter = not restricted
        userSupporter = True

        # Server restarting check
        if glob.restarting:
            raise exceptions.banchoRestartingException()

        # Send login notification before maintenance message
        if glob.banchoConf.config["loginNotification"]:
            await osuToken.enqueue(
                userToken["token_id"],
                serverPackets.notification(
                    glob.banchoConf.config["loginNotification"].format(
                        BUILD_VER=glob.latestBuild,
                    ),
                ),
            )

        # Maintenance check
        if glob.banchoConf.config["banchoMaintenance"]:
            if not userGMT:
                # We are not mod/admin, delete token, send notification and logout
                await tokenList.deleteToken(responseTokenString)
                raise exceptions.banchoMaintenanceException()
            else:
                # We are mod/admin, send warning notification and continue
                await osuToken.enqueue(
                    userToken["token_id"],
                    serverPackets.notification(
                        "Akatsuki is currently in maintenance mode. Only admins have full access to the server.\n"
                        "Type '!system maintenance off' in chat to turn off maintenance mode.",
                    ),
                )

        # Send all needed login packets
        await osuToken.enqueue(userToken["token_id"], serverPackets.protocolVersion(19))
        await osuToken.enqueue(userToken["token_id"], serverPackets.userID(userID))
        await osuToken.enqueue(
            userToken["token_id"],
            serverPackets.silenceEndTime(silenceSeconds),
        )
        await osuToken.enqueue(
            userToken["token_id"],
            serverPackets.userSupporterGMT(userSupporter, userGMT, userTournament),
        )
        await osuToken.enqueue(
            userToken["token_id"],
            await serverPackets.userPanel(userID, force=True),
        )
        await osuToken.enqueue(
            userToken["token_id"],
            await serverPackets.userStats(userID, force=True),
        )

        # Default opened channels.
        await chat.joinChannel(token_id=userToken["token_id"], channel_name="#osu")
        await chat.joinChannel(token_id=userToken["token_id"], channel_name="#announce")

        # Join role-related channels.
        if userToken["privileges"] & privileges.ADMIN_CAKER:
            await chat.joinChannel(
                token_id=userToken["token_id"],
                channel_name="#devlog",
            )
        if osuToken.is_staff(userToken["privileges"]):
            await chat.joinChannel(
                token_id=userToken["token_id"],
                channel_name="#staff",
            )
        if userToken["privileges"] & privileges.USER_PREMIUM:
            await chat.joinChannel(
                token_id=userToken["token_id"],
                channel_name="#premium",
            )
        if userToken["privileges"] & privileges.USER_DONOR:
            await chat.joinChannel(
                token_id=userToken["token_id"],
                channel_name="#supporter",
            )

        # Output channels info
        for channel in await channelList.getChannels():
            if channel["public_read"] and not channel["instance"]:
                client_count = await stream.getClientCount(f"chat/{channel['name']}")
                packet_data = serverPackets.channelInfo(
                    channel["name"],
                    channel["description"],
                    client_count,
                )
                await osuToken.enqueue(userToken["token_id"], packet_data)

        # Channel info end.
        await osuToken.enqueue(userToken["token_id"], serverPackets.channelInfoEnd)

        # Send friends list
        friends_list = await userUtils.getFriendList(userID)
        await osuToken.enqueue(
            userToken["token_id"],
            serverPackets.friendList(userID, friends_list),
        )

        # Send main menu icon
        if glob.banchoConf.config["menuIcon"]:
            await osuToken.enqueue(
                userToken["token_id"],
                serverPackets.mainMenuIcon(glob.banchoConf.config["menuIcon"]),
            )

        # Save token in redis
        await glob.redis.set(f"akatsuki:sessions:{responseTokenString}", userID)

        # Send online users' panels
        for token in await osuToken.get_tokens():
            if not osuToken.is_restricted(token["privileges"]):
                await osuToken.enqueue(
                    userToken["token_id"],
                    await serverPackets.userPanel(token["user_id"]),
                )

        # Get location and country from ip.zxq.co or database.
        if settings.LOCALIZE_ENABLE:
            # Get location and country from IP
            countryLetters, (latitude, longitude) = locationHelper.getGeoloc(requestIP)
            country = countryHelper.getCountryID(countryLetters)
        else:
            countryLetters = "XX"
            latitude = longitude = 0.0
            country = 0

        # Set location and country
        await osuToken.setLocation(userToken["token_id"], latitude, longitude)
        await osuToken.update_token(userToken["token_id"], country=country)

        # Set country in db if user has no country (first bancho login)
        if await userUtils.getCountry(userID) == "XX":
            await userUtils.setCountry(userID, countryLetters)

        # Send to everyone our userpanel if we are not restricted or tournament
        if not osuToken.is_restricted(userToken["privileges"]):
            await streamList.broadcast("main", await serverPackets.userPanel(userID))

        glob.amplitude.track(
            BaseEvent(
                event_type="osu_login",
                user_id=str(userID),
                device_id=userToken["amplitude_device_id"],
                event_properties={
                    "username": userToken["username"],
                    "privileges": userToken["privileges"],
                    "login_time": userToken["login_time"],
                    "source": "bancho-service",
                },
                location_lat=latitude,
                location_lng=longitude,
                ip=requestIP,
                country=countryLetters,
            ),
        )

        if firstLogin:
            glob.amplitude.track(
                BaseEvent(
                    event_type="osu_verification",
                    user_id=str(userID),
                    device_id=userToken["amplitude_device_id"],
                    event_properties={
                        "username": userToken["username"],
                        "privileges": userToken["privileges"],
                        "login_time": userToken["login_time"],
                        "source": "bancho-service",
                    },
                    location_lat=latitude,
                    location_lng=longitude,
                    ip=requestIP,
                    country=countryLetters,
                ),
            )

        identify_obj = Identify()
        identify_obj.set("username", userToken["username"])
        identify_obj.set("location_lat", latitude)
        identify_obj.set("location_lng", longitude)
        identify_obj.set("ip", requestIP)
        identify_obj.set("country", countryLetters)
        glob.amplitude.identify(
            identify_obj,
            EventOptions(
                user_id=str(userID),
                device_id=userToken["amplitude_device_id"],
            ),
        )

        # Set reponse data to right value and reset our queue
        responseData = await osuToken.dequeue(userToken["token_id"])
    except exceptions.loginFailedException:
        # Login failed error packet
        # (we don't use enqueue because we don't have a token since login has failed)
        responseData += serverPackets.loginFailed
        responseData += serverPackets.notification(
            "Akatsuki: You have entered an incorrect username or password. Please check your credentials and try again!",
        )
    except exceptions.invalidArgumentsException:
        # Invalid POST data
        # (we don't use enqueue because we don't have a token since login has failed)
        responseData += serverPackets.loginFailed
        responseData += serverPackets.notification(
            "Akatsuki: Something went wrong during your login attempt... Please try again!",
        )
    except exceptions.loginBannedException:
        # Login banned error packet
        responseData += serverPackets.loginBanned
    except exceptions.loginLockedException:
        # Login banned error packet
        responseData += serverPackets.loginLocked
    except exceptions.banchoMaintenanceException:
        # Bancho is in maintenance mode
        if userToken:
            responseData = await osuToken.dequeue(userToken["token_id"])
        else:
            responseData.clear()
        responseData += serverPackets.notification(
            "Akatsuki is currently in maintenance mode. Please try to login again later.",
        )
        responseData += serverPackets.loginFailed
    except exceptions.banchoRestartingException:
        # Bancho is restarting
        responseData += serverPackets.notification(
            "Akatsuki is restarting. Try again in a few minutes.",
        )
        responseData += serverPackets.loginFailed
    # except exceptions.need2FAException:
    #    # User tried to log in from unknown IP
    #    responseData += serverPackets.needVerification
    except exceptions.haxException:
        # Using old client, we don't have client data, force update (we don't use enqueue because we don't have a token since login has failed)
        responseData += serverPackets.loginFailed
        responseData += serverPackets.notification(
            "\n\n".join(
                [
                    "Hey!",
                    "The osu! client you're trying to use is out of date.",
                    "Custom/out of date osu! clients are not permitted on Akatsuki.",
                    "Please relogin using the current osu! client - no fallback, sorry!",
                    "You will need to switch to Bancho in order to update your client.",
                ],
            ),
        )

        if not restricted and (
            v_argstr in web_handler.request.arguments or osuVersionStr == v_argverstr
        ):
            await rap_logs.send_rap_log_as_discord_webhook(
                message=f"**[{username}](https://akatsuki.gg/u/{userID})** has attempted to login with the {v_argstr} client.",
                discord_channel="ac_general",
            )
    except:
        logging.exception("An unhandled exception occurred during login")
    finally:
        # Console and discord log
        if len(loginData) < 3:
            logging.warning(
                "Invalid bancho login request",
                extra={
                    "reason": "insufficient_post_data",
                    "ip": requestIP,
                },
            )
        # TODO: re-add discord webhook
        await rap_logs.send_rap_log_as_discord_webhook(
            message=f"Invalid bancho login request from **{requestIP}** (insufficient POST data)",
            discord_channel="ac_confidential",
        )

        # Return token string and data
        return responseTokenString, bytes(responseData)


v_argstr = bytes([97, 105, 110, 117]).decode()
v_argverstr = bytes([48, 65, 105, 110, 117]).decode()
