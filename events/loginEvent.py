from __future__ import annotations

import re
import time
from datetime import datetime as dt
from datetime import timedelta as td
from sys import exc_info
from traceback import format_exc
from typing import TYPE_CHECKING

from cmyui.logging import Ansi
from cmyui.logging import log
from fastapi import Request

import settings
from common import generalUtils
from common.constants import privileges
from common.log import logUtils
from common.ripple import userUtils
from constants import exceptions
from constants import serverPackets
from helpers import chatHelper as chat
from helpers import countryHelper
from helpers import locationHelper
from objects import glob

osu_ver_regex = re.compile(
    r"^b(?P<ver>\d{8})(?:\.(?P<subver>\d))?"
    r"(?P<stream>beta|cuttingedge|dev|tourney)?$",
)


async def handle(
    request: Request,
) -> tuple[str, bytes]:  # token, data
    try:
        # Data to return
        responseToken = None
        responseTokenString = "ayy"
        responseData = bytearray()

        # Get IP from tornado request
        if "CF-Connecting-IP" in request.headers:
            requestIP = request.headers.get("CF-Connecting-IP")
        elif "X-Forwarded-For" in request.headers:
            requestIP = request.headers.get("X-Forwarded-For")
        else:
            print("No IP provided?")
            raise exceptions.invalidArgumentsException()

        # Split POST body so we can get username/password/hardware data
        loginData = (await request.body()).decode()[:-1].split("\n")

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
        timeOffset = int(splitData[1])
        if len(clientData := splitData[3].split(":")[:5]) < 4:
            raise exceptions.forceUpdateException()
        blockNonFriendsDM = splitData[4] == "1"

        # Try to get the ID from username
        username = loginData[0]
        userID = userUtils.getID(username)

        if not userID:
            # Invalid username
            raise exceptions.loginFailedException()
        elif userID == 999:
            raise exceptions.invalidArgumentsException()

        if not userUtils.checkLogin(userID, loginData[1]):
            # Invalid password
            raise exceptions.loginFailedException()

        # Make sure we are not banned or locked
        priv = userUtils.getPrivileges(userID)
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

        if v_argstr in request.request.arguments or osuVersionStr == v_argverstr:
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
            log(f"Denied login from {osuVersionStr}.", Ansi.LYELLOW)
            raise exceptions.haxException()

        """ No login errors! """

        # Verify this user (if pending activation)
        firstLogin = False
        if pending_verification or not userUtils.hasVerifiedHardware(userID):
            if userUtils.verifyUser(userID, clientData):
                # Valid account
                log(f"{username} ({userID}) verified successfully!", Ansi.LGREEN)
                glob.verifiedCache[str(userID)] = 1
                firstLogin = True
            else:
                # Multiaccount detected
                log(
                    f"{username} ({userID}) tried to create another account.",
                    Ansi.LRED,
                )
                glob.verifiedCache[str(userID)] = 0
                raise exceptions.loginBannedException()

        # Save HWID in db for multiaccount detection
        hwAllowed = userUtils.logHardware(userID, clientData, firstLogin)

        # This is false only if HWID is empty
        # if HWID is banned, we get restricted so there's no
        # need to deny bancho access
        if not hwAllowed:
            raise exceptions.haxException()

        # Log user IP
        userUtils.logIP(userID, requestIP)

        # Delete old tokens for that user and generate a new one
        isTournament = rgx["stream"] == "tourney"

        with glob.tokens:
            if not isTournament:
                glob.tokens.deleteOldTokens(userID)
            responseToken = glob.tokens.addToken(
                userID,
                requestIP,
                timeOffset=timeOffset,
                tournament=isTournament,
            )
        responseToken.blockNonFriendsDM = blockNonFriendsDM
        responseTokenString = responseToken.token

        # Console output
        log(
            f"{username} ({userID}) logged in. "
            f"({len(glob.tokens.tokens) - 1} online)",
            Ansi.CYAN,
        )

        # Check restricted mode (and eventually send message)
        responseToken.checkRestricted()

        """ osu!Akatuki account freezing. """

        # Get the user's `frozen` status from the DB
        # For a normal user, this will return 0.
        # For a frozen user, this will return a unix timestamp (the date of their pending restriction).
        freeze_timestamp = userUtils.getFreezeTime(userID)
        current_time = int(time.time())

        if freeze_timestamp:
            if freeze_timestamp == 1:  # Begin the timer.
                freeze_timestamp = userUtils.beginFreezeTimer(userID)

            reason = userUtils.getFreezeReason(userID)
            freeze_str = f" as a result of:\n\n{reason}\n" if reason else ""

            if freeze_timestamp > current_time:  # We are warning the user
                chat.sendMessage(
                    glob.BOT_NAME,
                    username,
                    "\n".join(
                        [
                            f"Your account has been frozen by an administrator{freeze_str}",
                            "This is not a restriction, but will lead to one if ignored.",
                            "You are required to submit a liveplay using the (specified criteria)[https://pastebin.com/BwcXp6Cr]",
                            "Please remember we are not stupid - we have done plenty of these before and have heard every excuse in the book; if you are breaking rules, your best bet would be to admit to a staff member, lying will only end up digging your grave deeper.",
                            "-------------",
                            "If you have any questions or are ready to liveplay, please contact an (Akatsuki Administrator)[https://akatsuki.pw/team] {ingame, (Discord)[https://akatsuki.pw/discord], etc.}",
                            f"Time until account restriction: {td(seconds = freeze_timestamp - current_time)}.",
                        ],
                    ),
                )

            else:  # We are restricting the user
                # TODO: perhaps move this to the cron?
                # right now a user can avoid a resitrction by simply not logging in lol..
                userUtils.restrict(userID)
                userUtils.unfreeze(userID, _log=False)

                responseToken.enqueue(
                    serverPackets.notification(
                        "\n\n".join(
                            [
                                "Your account has been automatically restricted due to an account freeze being left unhandled for over 7 days.",
                                "You are still welcome to liveplay, although your account will remain in restricted mode unless this is handled.",
                            ],
                        ),
                    ),
                )
                logUtils.rap(
                    userID,
                    "has been automatically restricted due to a pending freeze.",
                )
                logUtils.ac(
                    f"[{username}](https://akatsuki.pw/u/{userID}) has been automatically restricted due to a pending freeze.",
                    "ac_general",
                )

        # Send message if premium / donor expires soon
        # This should NOT be done at login, but done by the cron
        if responseToken.privileges & privileges.USER_DONOR:
            expireDate = userUtils.getDonorExpire(userID)
            premium = responseToken.privileges & privileges.USER_PREMIUM
            rolename = "premium" if premium else "supporter"

            if current_time >= expireDate:
                userUtils.setPrivileges(
                    userID,
                    responseToken.privileges - privileges.USER_DONOR
                    | (privileges.USER_PREMIUM if premium else 0),
                )

                # 36 = supporter, 59 = premium
                badges = glob.db.fetchAll(
                    "SELECT id FROM user_badges WHERE badge IN (59, 36) AND user = %s",
                    [userID],
                )
                if badges:
                    for (
                        badge
                    ) in badges:  # Iterate through user badges, deleting them all
                        glob.db.execute(
                            "DELETE FROM user_badges WHERE id = %s",
                            [badge["id"]],
                        )

                # Remove their custom privileges
                glob.db.execute(
                    "UPDATE users_stats set can_custom_badge = 0, show_custom_badge = 0 WHERE id = %s",
                    [userID],
                )

                logUtils.ac(
                    f"[{username}](https://akatsuki.pw/u/{userID})'s {rolename} subscription has expired.",
                    "ac_confidential",
                )
                logUtils.rap(userID, f"{rolename} subscription expired.")

                responseToken.enqueue(
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
                responseToken.enqueue(
                    serverPackets.notification(
                        f"Your {rolename} tag expires in {expireIn}.",
                    ),
                )

        # Set silence end UNIX time in token
        responseToken.silenceEndTime = userUtils.getSilenceEnd(userID)

        # Get only silence remaining seconds
        silenceSeconds = responseToken.getSilenceSecondsLeft()

        # Get supporter/GMT
        userGMT = responseToken.staff
        userTournament = responseToken.privileges & privileges.USER_TOURNAMENT_STAFF > 0

        # userSupporter = not restricted
        userSupporter = True

        # Server restarting check
        if glob.restarting:
            raise exceptions.banchoRestartingException()

        # Send login notification before maintenance message
        if glob.banchoConf.config["loginNotification"]:
            responseToken.enqueue(
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
                glob.tokens.deleteToken(responseTokenString)
                raise exceptions.banchoMaintenanceException()
            else:
                # We are mod/admin, send warning notification and continue
                responseToken.enqueue(
                    serverPackets.notification(
                        "Akatsuki is currently in maintenance mode. Only admins have full access to the server.\n"
                        "Type '!system maintenance off' in chat to turn off maintenance mode.",
                    ),
                )

        # Send all needed login packets
        responseToken.enqueue(serverPackets.protocolVersion(19))
        responseToken.enqueue(serverPackets.userID(userID))
        responseToken.enqueue(serverPackets.silenceEndTime(silenceSeconds))
        responseToken.enqueue(
            serverPackets.userSupporterGMT(userSupporter, userGMT, userTournament),
        )
        responseToken.enqueue(serverPackets.userPanel(userID, force=True))
        responseToken.enqueue(serverPackets.userStats(userID, force=True))

        # Default opened channels.
        chat.joinChannel(token=responseToken, channel="#osu")
        chat.joinChannel(token=responseToken, channel="#announce")

        # Join role-related channels.
        if responseToken.privileges & privileges.ADMIN_CAKER:
            chat.joinChannel(token=responseToken, channel="#devlog")
        if responseToken.staff:
            chat.joinChannel(token=responseToken, channel="#staff")
        if responseToken.privileges & privileges.USER_PREMIUM:
            chat.joinChannel(token=responseToken, channel="#premium")
        if responseToken.privileges & privileges.USER_DONOR:
            chat.joinChannel(token=responseToken, channel="#supporter")

        # Output channels info
        for key, value in glob.channels.channels.items():
            if value.publicRead and not value.hidden:
                responseToken.enqueue(serverPackets.channelInfo(key))

        # Channel info end.
        responseToken.enqueue(serverPackets.channelInfoEnd)

        # Send friends list
        responseToken.enqueue(serverPackets.friendList(userID))

        # Send main menu icon
        if glob.banchoConf.config["menuIcon"]:
            responseToken.enqueue(
                serverPackets.mainMenuIcon(
                    f'{glob.banchoConf.config["menuIcon"]}/u/{userID}',
                ),
            )

        # Save token in redis
        glob.redis.set(f"akatsuki:sessions:{responseTokenString}", userID)

        # Send online users' panels
        with glob.tokens:
            for token in glob.tokens.tokens.values():
                if not token.restricted:
                    responseToken.enqueue(serverPackets.userPanel(token.userID))

        # Get location and country from ip.zxq.co or database. If the user is a donor, then yee
        if settings.LOCALIZE_ENABLE and (
            firstLogin or not responseToken.privileges & privileges.USER_DONOR
        ):
            # Get location and country from IP
            countryLetters, (latitude, longitude) = locationHelper.getGeoloc(requestIP)
            country = countryHelper.getCountryID(countryLetters)
        else:
            # Set location to 0,0 and get country from db
            latitude = 0.0
            longitude = 0.0
            countryLetters = "XX"
            country = countryHelper.getCountryID(userUtils.getCountry(userID))

        # Set location and country
        responseToken.setLocation(latitude, longitude)
        responseToken.country = country

        # Set country in db if user has no country (first bancho login)
        if userUtils.getCountry(userID) == "XX":
            userUtils.setCountry(userID, countryLetters)

        # Send to everyone our userpanel if we are not restricted or tournament
        if not responseToken.restricted:
            glob.streams.broadcast("main", serverPackets.userPanel(userID))

        # Set reponse data to right value and reset our queue
        responseData = responseToken.queue.copy()
        responseToken.resetQueue()
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
        if responseToken:
            responseData = responseToken.queue.copy()
            responseToken.resetQueue()
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
                ],
            ),
        )

        if not restricted and (
            v_argstr in request.request.arguments or osuVersionStr == v_argverstr
        ):
            logUtils.ac(
                f"**[{username}](https://akatsuki.pw/u/{userID})** has attempted to login with the {v_argstr} client.",
                "ac_general",
            )
    except:
        log(f"Unknown error\n```\n{exc_info()}\n{format_exc()}```", Ansi.LRED)
    finally:
        # Console and discord log
        if len(loginData) < 3:
            logUtils.ac(
                f"Invalid bancho login request from **{requestIP}** (insufficient POST data)",
                "ac_confidential",
            )

        # Return token string and data
        return responseTokenString, bytes(responseData)


v_argstr = bytes([97, 105, 110, 117]).decode()
v_argverstr = bytes([48, 65, 105, 110, 117]).decode()
