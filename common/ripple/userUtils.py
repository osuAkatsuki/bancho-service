from __future__ import annotations

import time
from time import localtime
from time import strftime
from typing import Any
from typing import Optional
from typing import TypedDict

import bcrypt

from common.constants import gameModes
from common.constants import privileges
from common.log import audit_logs
from common.log import logger
from constants import CHATBOT_USER_ID
from objects import glob


async def getPlaytimeTotal(userID: int) -> int:
    """
    Get a users playtime for all gameModes combined.

    :param userID:
    """

    res = await glob.db.fetch(
        """
        SELECT SUM(playtime) AS total_playtime
        FROM user_stats
        WHERE user_id = %s
        """,
        [userID],
    )
    return res["total_playtime"] if res else 0


async def editWhitelist(userID: int, bit: int) -> None:
    """
    Change a userID's whitelist status to bit.

    bit 0 =
    bit 1 = vanilla
    bit 2 = relax
    bit 3 = vanilla & relax
    """

    await glob.db.execute(
        "UPDATE users SET whitelist = %s WHERE id = %s",
        [bit, userID],
    )


class UserStatsResponse(TypedDict):
    ranked_score: int
    avg_accuracy: float
    playcount: int
    total_score: int
    pp: int
    global_rank: int


async def getUserStats(
    userID: int,
    gameMode: int,
    relax_ap: int,
) -> Optional[UserStatsResponse]:
    """
    Get all user stats relative to `gameMode`.

    :param userID:
    :param gameMode: game mode number
    :return: dictionary with result
    """

    # Get stats
    stats = await glob.db.fetch(
        """
        SELECT ranked_score, avg_accuracy, playcount, total_score, pp
        FROM user_stats
        WHERE user_id = %s AND mode = %s
        """,
        [userID, gameMode + (relax_ap * 4)],
    )
    if stats is None:
        logger.warning(
            "Stats row missing for user",
            extra={
                "user_id": userID,
                "game_mode": gameMode,
                "relax_ap": relax_ap,
            },
        )
        return None

    # Get game rank
    stats["global_rank"] = await getGameRank(userID, gameMode, relax_ap)

    # Return stats + game rank
    return stats


async def getIDSafe(_safeUsername: str) -> Optional[int]:
    """
    Get user ID from a safe username
    :param _safeUsername: safe username
    :return: None if the user doesn't exist, else user id
    """

    result = await glob.db.fetch(
        "SELECT id " "FROM users " "WHERE username_safe = %s",
        [_safeUsername],
    )

    return result["id"] if result else None


async def getMapNominator(beatmapID: int) -> Optional[Any]:
    """
    Get the user who ranked a map by beatmapID.
    """

    res = await glob.db.fetch(
        "SELECT song_name, ranked, rankedby " "FROM beatmaps WHERE beatmap_id = %s",
        [beatmapID],
    )

    return res if res else None


async def getID(username: str) -> int:
    """
    Get username's user ID from userID redis cache (if cache hit)
    or from db (and cache it for other requests) if cache miss

    :param username: user
    :return: user id or 0 if user doesn't exist
    """

    # Get userID from redis
    usernameSafe: str = safeUsername(username)
    userID = await glob.redis.get(f"ripple:userid_cache:{usernameSafe}")

    if not userID:
        # If it's not in redis, get it from mysql
        userID = await getIDSafe(usernameSafe)

        # If it's invalid, return 0
        if not userID:
            return 0

        # Otherwise, save it in redis and return it
        await glob.redis.set(
            f"ripple:userid_cache:{usernameSafe}",
            userID,
            3600,
        )  # expires in 1 hour
        return userID

    # Return userid from redis
    return int(userID)


async def getUsername(userID: int) -> Optional[str]:
    """
    Get userID's username.

    :param userID: user id
    :return: username or None
    """

    result = await glob.db.fetch(
        "SELECT username " "FROM users " "WHERE id = %s",
        [userID],
    )

    return result["username"] if result else None


async def checkLogin(userID: int, password: str, ip: str = "") -> bool:
    """
    Check userID's login with specified password.

    :param userID: user id
    :param password: md5 password
    :param ip: request IP (used to check active bancho sessions). Optional.
    :return: True if user id and password combination is valid, else False
    """

    # Check cached bancho session
    banchoSession = False
    if ip:
        banchoSession = await checkBanchoSessionIpLookup(userID, ip)

    # Return True if there's a bancho session for this user from that ip
    if banchoSession:
        return True

    # Otherwise, check password
    # Get password data
    passwordData = await glob.db.fetch(
        "SELECT password_md5 FROM users WHERE id = %s LIMIT 1",
        [userID],
    )

    # Make sure the query returned something
    if not passwordData:
        return False

    pw_md5 = password.encode()
    db_pw_bcrypt = passwordData["password_md5"].encode()  # why is it called md5 LOL

    if db_pw_bcrypt in glob.bcrypt_cache:  # ~0.01ms
        return pw_md5 == glob.bcrypt_cache[db_pw_bcrypt]
    elif bcrypt.checkpw(pw_md5, db_pw_bcrypt):  # ~200ms
        glob.bcrypt_cache[db_pw_bcrypt] = pw_md5
        return True

    return False


async def getPP(userID: int, gameMode: int, relax: bool, autopilot: bool) -> int:
    """
    Get userID's PP relative to gameMode.

    :param userID: user id
    :param gameMode: game mode number
    :return: pp
    """
    assert not (relax and autopilot)
    mode_offset = (4 if relax else 0) + (8 if autopilot else 0)
    result = await glob.db.fetch(
        """
        SELECT pp
        FROM user_stats
        WHERE user_id = %s
        AND mode = %s
        """,
        [userID, gameMode + mode_offset],
    )
    return result[f"pp"] if result else 0


async def checkBanchoSessionIpLookup(userID: int, ip: str = ""):
    """
    Return True if there is a bancho session for `userID` from `ip`
    If `ip` is an empty string, check if there's a bancho session for that user, from any IP.

    :param userID: user id
    :param ip: ip address. Optional. Default: empty string
    :return: True if there's an active bancho session, else False
    """
    if ip:
        return await glob.redis.sismember(f"bancho:sessions_by_ip:{userID}", ip)
    else:
        return await glob.redis.exists(f"bancho:sessions_by_ip:{userID}")


async def isAllowed(userID: int) -> bool:
    """
    Check if userID is not banned or restricted

    :param userID: user id
    :return: True if not banned or restricted, otherwise false.
    """

    return (
        await glob.db.fetch(
            "SELECT 1 FROM users " "WHERE id = %s " "AND privileges & 3 = 3",
            [userID],
        )
        is not None
    )


async def isRestricted(userID: int) -> bool:
    """
    Check if userID is restricted

    :param userID: user id
    :return: True if not restricted, otherwise false.
    """

    return (
        await glob.db.fetch(
            "SELECT 1 FROM users "
            "WHERE id = %s "
            "AND privileges & 1 = 0 "  # hidden profile
            "AND privileges & 2 != 0",  # has account access
            [userID],
        )
        is not None
    )


async def isBanned(userID: int) -> bool:
    """
    Check if userID is banned

    :param userID: user id
    :return: True if not banned, otherwise false.
    """

    return (
        await glob.db.fetch(
            "SELECT 1 FROM users "
            "WHERE id = %s "
            "AND privileges & 3 = 0",  # no access, hidden profile
            [userID],
        )
        is not None
    )


async def ban(userID: int) -> None:
    """
    Ban userID

    :param userID: user id
    :return:
    """

    # Set user as banned in db
    await glob.db.execute(
        "UPDATE users "
        "SET privileges = privileges & %s, "
        "ban_datetime = UNIX_TIMESTAMP() "
        "WHERE id = %s",
        [
            ~(
                privileges.USER_NORMAL
                | privileges.USER_PUBLIC
                | privileges.USER_PENDING_VERIFICATION
            ),
            userID,
        ],
    )

    # Notify bancho about the ban
    await glob.redis.publish("peppy:ban", userID)

    # Remove the user from global and country leaderboards
    await removeFromLeaderboard(userID)


async def unban(userID: int) -> None:
    """
    Unban userID

    :param userID: user id
    :return:
    """

    await glob.db.execute(
        "UPDATE users "
        "SET privileges = privileges | %s, "
        "ban_datetime = 0 "
        "WHERE id = %s",
        [privileges.USER_NORMAL | privileges.USER_PUBLIC, userID],
    )

    await glob.redis.publish("peppy:unban", userID)


async def restrict(userID: int) -> None:
    """
    Restrict userID

    :param userID: user id
    :return:
    """
    if not await isRestricted(userID):
        # Set user as restricted in db
        await glob.db.execute(
            "UPDATE users SET privileges = privileges & %s, "
            "ban_datetime = UNIX_TIMESTAMP() WHERE id = %s",
            [~privileges.USER_PUBLIC, userID],
        )

        # Notify bancho about this ban
        await glob.redis.publish("peppy:ban", userID)

        # Remove the user from global and country leaderboards
        await removeFromLeaderboard(userID)


async def unrestrict(userID: int) -> None:
    """
    Unrestrict userID.
    Same as unban().

    :param userID: user id
    :return:
    """

    await unban(userID)


async def appendNotes(
    userID: int,
    notes: str,
    addNl: bool = True,
    trackDate: bool = True,
) -> None:
    """
    Append `notes` to `userID`'s "notes for CM"

    :param userID: user id
    :param notes: text to append
    :param addNl: if True, prepend \n to notes. Default: True.
    :param trackDate: if True, prepend date and hour to the note. Default: True.
    :return:
    """

    if trackDate:
        notes = f"[{strftime('%Y-%m-%d %H:%M:%S', localtime())}] {notes}"

    if addNl:
        notes = f"\n{notes}"

    await glob.db.execute(
        "UPDATE users " 'SET notes = CONCAT(COALESCE(notes, ""), %s) ' "WHERE id = %s",
        [notes, userID],
    )


async def getPrivileges(userID: int) -> int:
    """
    Return `userID`'s privileges

    :param userID: user id
    :return: privileges number
    """

    result = await glob.db.fetch(
        "SELECT privileges " "FROM users " "WHERE id = %s",
        [userID],
    )

    return result["privileges"] if result else 0


async def getFreezeTime(userID: int) -> int:
    """
    Return a `userID`'s enqueued restriction date.

    :param userID: userID of the target (restrictee)
    :return: timestamp
    """

    result = await glob.db.fetch(
        "SELECT frozen " "FROM users " "WHERE id = %s",
        [userID],
    )

    return result["frozen"] if result else 0


async def getFreezeReason(userID: int) -> Optional[str]:
    result = await glob.db.fetch(
        "SELECT freeze_reason FROM users WHERE id = %s",
        [userID],
    )
    return result["freeze_reason"] if result["freeze_reason"] else None


async def freeze(userID: int, author: int = CHATBOT_USER_ID) -> None:
    """
    Enqueue a 'pending' restriction on a user. (7 days)
    Used for getting liveplays from users already suspected of cheating.

    :param userID: userID of the target (restrictee)
    :param author: userID of the author (restricter)
    """

    await beginFreezeTimer(userID)  # to fix cron bugs

    author_name = await getUsername(author)
    target_name = await getUsername(userID)

    await appendNotes(userID, f"{author_name} ({author}) froze this user.")
    await audit_logs.send_log(author, f"froze {target_name} ({userID}).")
    await audit_logs.send_log_as_discord_webhook(
        message=f"{author_name} has frozen [{target_name}](https://akatsuki.gg/u/{userID}).",
        discord_channel="ac_general",
    )


async def beginFreezeTimer(userID) -> int:
    restriction_time = int(time.time() + (86400 * 7))

    await glob.db.execute(
        "UPDATE users SET frozen = %s " "WHERE id = %s",
        [restriction_time, userID],
    )

    return restriction_time  # Return so we can update the time


async def unfreeze(userID: int, author: int = CHATBOT_USER_ID, _log=True) -> None:
    """
    Dequeue a 'pending' restriction on a user.

    :param userID: userID of the target (restrictee)
    :param author: userID of the author (restricter)
    """

    await glob.db.execute(
        "UPDATE users " "SET frozen = 0, freeze_reason = '' WHERE id = %s",
        [userID],
    )

    if _log:
        author_name = await getUsername(author)
        target_name = await getUsername(userID)

        await appendNotes(userID, f"{author_name} ({author}) unfroze this user.")
        await audit_logs.send_log(author, f"unfroze {target_name} ({userID}).")
        await audit_logs.send_log_as_discord_webhook(
            message=f"{author_name} has unfrozen [{target_name}](https://akatsuki.gg/u/{userID}).",
            discord_channel="ac_general",
        )


async def getSilenceEnd(userID: int) -> int:
    """
    Get userID's **ABSOLUTE** silence end UNIX time
    Remember to subtract time.time() if you want to get the actual silence time

    :param userID: user id
    :return: UNIX time
    """

    rec = await glob.db.fetch(
        "SELECT silence_end " "FROM users " "WHERE id = %s",
        [userID],
    )
    return rec["silence_end"]


async def silence(
    userID: int,
    seconds: int,
    silenceReason: str,
    author: int = CHATBOT_USER_ID,
) -> None:
    """
    Silence `userID` for `seconds` for `silenceReason`.

    :param userID: user id
    :param seconds: silence length in seconds
    :param silenceReason: silence reason shown on website
    :param author: userID of who silenced the user. Default: CHATBOT_USER_ID
    :return:
    """

    silence_time = int(time.time() + seconds)

    await glob.db.execute(
        "UPDATE users " "SET silence_end = %s, silence_reason = %s " "WHERE id = %s",
        [silence_time, silenceReason, userID],
    )

    await audit_logs.send_log(
        author,
        (
            f'has silenced {await getUsername(userID)} for {seconds} seconds for the following reason: "{silenceReason}"'
            if seconds
            else f"has removed {await getUsername(userID)}'s silence"
        ),
    )


async def getGameRank(userID: int, gameMode: int, relax_ap: int) -> int:
    """
    Get `userID`'s **in-game rank** (eg: #1337) relative to gameMode

    :param userID: user id
    :param gameMode: game mode number
    :return: game rank
    """

    board = "leaderboard"
    if relax_ap == 1:
        board = "relaxboard"
    elif relax_ap == 2:
        board = "autoboard"

    position = await glob.redis.zrevrank(
        f"ripple:{board}:{gameModes.getGameModeForDB(gameMode)}",
        userID,
    )

    return int(position) + 1 if position is not None else 0


async def getFriendList(userID: int):
    """
    Get `userID`'s friendlist

    :param userID: user id
    :return: list with friends userIDs. [0] if no friends.
    """

    # Get friends from db
    # TODO: tuple cursor support? or use cmyui.mysql sync ver/make this native async
    friends = await glob.db.fetchAll(
        "SELECT user2 " "FROM users_relationships " "WHERE user1 = %s",
        [userID],
    )

    if not friends or not len(friends):
        # We have no friends, return 0 list
        return [0]
    else:
        # Get only friends
        friends = [i["user2"] for i in friends]

        # Return friend IDs
        return friends


async def addFriend(userID: int, friendID: int) -> None:
    """
    Add `friendID` to `userID`'s friend list

    :param userID: user id
    :param friendID: new friend
    :return:
    """

    # Make sure we aren't adding ourselves
    if userID == friendID:
        return

    # Check user isn't already a friend of ours
    if await glob.db.fetch(
        "SELECT id " "FROM users_relationships " "WHERE user1 = %s AND user2 = %s",
        [userID, friendID],
    ):
        return

    # Set new value
    await glob.db.execute(
        "INSERT INTO users_relationships " "(user1, user2) VALUES (%s, %s)",
        [userID, friendID],
    )


async def removeFriend(userID: int, friendID: int) -> None:
    """
    Remove `friendID` from `userID`'s friend list

    :param userID: user id
    :param friendID: old friend
    :return:
    """

    # Delete user relationship. We don't need to check if the relationship was there, because who gives a shit,
    # if they were not friends and they don't want to be anymore, be it. ¯\_(ツ)_/¯
    await glob.db.execute(
        "DELETE FROM users_relationships WHERE user1 = %s AND user2 = %s",
        [userID, friendID],
    )


async def getCountry(userID: int) -> str:
    """
    Get `userID`'s country **(two letters)**.

    :param userID: user id
    :return: country code (two letters)
    """

    rec = await glob.db.fetch(
        "SELECT country FROM users WHERE id = %s",
        [userID],
    )
    return rec["country"]


async def setCountry(userID: int, country: str) -> None:
    """
    Set userID's country

    :param userID: user id
    :param country: country letters
    :return:
    """

    await glob.db.execute(
        "UPDATE users SET country = %s WHERE id = %s",
        [country, userID],
    )


async def logIP(userID: int, ip: str) -> None:
    """
    User IP log
    USED FOR MULTIACCOUNT DETECTION

    :param userID: user id
    :param ip: IP address
    :return:
    """

    await glob.db.execute(
        "INSERT INTO ip_user (userid, ip, occurencies) VALUES (%s, %s, 1) "
        "ON DUPLICATE KEY UPDATE occurencies = occurencies + 1",
        [userID, ip],
    )


async def saveBanchoSessionIpLookup(userID: int, ip: str) -> None:
    await glob.redis.sadd(f"bancho:sessions_by_ip:{userID}", ip)


async def deleteBanchoSessionIpLookup(userID: int, ip: str) -> None:
    await glob.redis.srem(f"bancho:sessions_by_ip:{userID}", ip)


async def setPrivileges(userID: int, priv: int) -> None:
    """
    Set userID's privileges in db

    :param userID: user id
    :param priv: privileges number
    :return:
    """

    await glob.db.execute(
        "UPDATE users " "SET privileges = %s " "WHERE id = %s",
        [priv, userID],
    )


async def compareHWID(userID: int, mac: str, unique: str, disk: str) -> bool:
    """
    Compare a user's login hwid's against what are stored in the db for admin account security.

    :param userID: The user's userID
    :param mac: The given MAC address
    :param unique: The given unique address
    :param disk: The given disk address
    """

    allowed = await glob.db.fetch(
        "SELECT * FROM hw_comparison " "WHERE id = %s",
        [userID],
    )

    return not (
        allowed
        and (
            mac != allowed["mac"]
            or unique != allowed["unique"]
            or disk != allowed["disk"]
        )
    )


async def logHardware(userID: int, hashes: list[str], activation: bool = False) -> bool:
    """
    Hardware log
    USED FOR MULTIACCOUNT DETECTION

    :param userID: user id
    :param hashes:	Peppy's botnet (client data) structure (new line = "|", already split)
                    [0] osu! version
                    [1] plain mac addressed, separated by "."
                    [2] mac addresses hash set
                    [3] unique ID
                    [4] disk ID
    :param activation: if True, set this hash as used for activation. Default: False.
    :return: True if hw is not banned, otherwise false
    """

    # Get username
    username = await getUsername(userID)

    # Make sure the strings are not empty
    for i in hashes[2:5]:
        if not i:
            await audit_logs.send_log_as_discord_webhook(
                message=f"Invalid hash set ({hashes}) for user [{username}](https://akatsuki.gg/u/{userID}) in HWID check",
                discord_channel="ac_confidential",
            )
            return False

    # Run some HWID checks on that user if he is not restricted
    if not await isRestricted(userID):
        """
        compare_ids = compareHWID(userID, hashes[2], hashes[3], hashes[4])

        if not compare_ids: # Remove cmyui permissions if on a HWID different than usual.. Just safety procautions..
            log.anticheat("{}: Unusual login detected.\n\nHashes:\nMAC: {}\nUnique: {}\nDisk: {}\n\nTheir login has been disallowed.".format(userID, hashes[2], hashes[3], hashes[4]), 'ac_confidential')
            return False
        """

        # Get the list of banned or restricted users that have logged in from this or similar HWID hash set
        if hashes[2] == "b4ec3c4334a0249dae95c284ec5983df":
            # Running under wine, check by unique id
            logger.debug("Logging Linux/Mac hardware")
            banned = await glob.db.fetchAll(
                """SELECT users.id as userid, hw_user.occurencies, users.username FROM hw_user
                LEFT JOIN users ON users.id = hw_user.userid
                WHERE hw_user.userid != %(userid)s
                AND hw_user.unique_id = %(uid)s
                AND (users.privileges & 3 != 3)""",
                {
                    "userid": userID,
                    "uid": hashes[3],
                },
            )
        else:
            # Running under windows, do all checks
            logger.debug("Logging Windows hardware")
            banned = await glob.db.fetchAll(
                """SELECT users.id as userid, hw_user.occurencies, users.username FROM hw_user
                LEFT JOIN users ON users.id = hw_user.userid
                WHERE hw_user.userid != %(userid)s
                AND hw_user.mac = %(mac)s
                AND hw_user.unique_id = %(uid)s
                AND hw_user.disk_id = %(diskid)s
                AND (users.privileges & 3 != 3)""",
                {
                    "userid": userID,
                    "mac": hashes[2],
                    "uid": hashes[3],
                    "diskid": hashes[4],
                },
            )

        banned_ids = []
        for i in banned:
            if i["userid"] in banned_ids:
                continue

            # Get the total numbers of logins
            total = await glob.db.fetch(
                "SELECT COUNT(*) AS count FROM hw_user WHERE userid = %s",
                [userID],
            )
            # and make sure it is valid
            if not total:
                continue
            total = total["count"]

            # Calculate 10% of total
            if i["occurencies"] >= (total * 10) / 100:
                # If the banned user has logged in more than 10% of the times from this user, restrict this user
                await restrict(userID)
                await appendNotes(
                    userID,
                    f'Logged in from HWID set used more than 10% from user {i["username"],} ({i["userid"]}), who is banned/restricted.',
                )
                await audit_logs.send_log_as_discord_webhook(
                    message=f'[{username}](https://akatsuki.gg/u/{userID}) has been restricted because he has logged in from HWID set used more than 10% from banned/restricted user [{i["username"]}](https://akatsuki.gg/u/{i["userid"]}), **possible multiaccount**.',
                    discord_channel="ac_general",
                )
            banned_ids.append(i["userid"])

    # Update hash set occurencies
    await glob.db.execute(
        """
                INSERT INTO hw_user (id, userid, mac, unique_id, disk_id, occurencies) VALUES (NULL, %s, %s, %s, %s, 1)
                ON DUPLICATE KEY UPDATE occurencies = occurencies + 1
                """,
        [userID, hashes[2], hashes[3], hashes[4]],
    )

    # Optionally, set this hash as 'used for activation'
    if activation:
        await glob.db.execute(
            "UPDATE hw_user SET activated = 1 WHERE userid = %s AND mac = %s AND unique_id = %s AND disk_id = %s",
            [userID, hashes[2], hashes[3], hashes[4]],
        )

    # Access granted, abbiamo impiegato 3 giorni
    # We grant access even in case of login from banned HWID
    # because we call restrict() above so there's no need to deny the access.
    return True


async def resetPendingFlag(userID: int, success: bool = True) -> None:
    """
    Remove pending flag from an user.

    :param userID: user id
    :param success: if True, set USER_PUBLIC and USER_NORMAL flags too
    """

    await glob.db.execute(
        "UPDATE users " "SET privileges = privileges & %s " "WHERE id = %s",
        [~privileges.USER_PENDING_VERIFICATION, userID],
    )

    if success:
        await glob.db.execute(
            "UPDATE users " "SET privileges = privileges | %s " "WHERE id = %s",
            [privileges.USER_PUBLIC | privileges.USER_NORMAL, userID],
        )


async def verifyUser(userID: int, hashes: list[str]) -> bool:
    """
    Activate `userID`'s account.

    :param userID: user id
    :param hashes: 	Peppy's botnet (client data) structure (new line = "|", already split)
                    [0] osu! version
                    [1] plain mac addressed, separated by "."
                    [2] mac addresses hash set
                    [3] unique ID
                    [4] disk ID
    :return: True if verified successfully, else False (multiaccount)
    """

    # Get username
    username = await getUsername(userID)

    # Check for valid hash set
    for i in hashes[2:5]:
        if i == "":
            await audit_logs.send_log_as_discord_webhook(
                message=f"Invalid hash set ({' | '.join(hashes)}) for user [{username}](https://akatsuki.gg/u/{userID}) while verifying the account",
                discord_channel="ac_confidential",
            )
            return False

    # Make sure there are no other accounts activated with this exact mac/unique id/hwid
    if (
        hashes[2] == "b4ec3c4334a0249dae95c284ec5983df"
        or hashes[4] == "ffae06fb022871fe9beb58b005c5e21d"
    ):
        # Running under wine, check only by uniqueid
        await audit_logs.send_log_as_discord_webhook(
            message=f"[{username}](https://akatsuki.gg/u/{userID}) running under wine:\n**Full data:** {hashes}\n**Usual wine mac address hash:** b4ec3c4334a0249dae95c284ec5983df\n**Usual wine disk id:** ffae06fb022871fe9beb58b005c5e21d",
            discord_channel="ac_confidential",
        )
        logger.debug("Veryfing with Linux/Mac hardware")
        match = await glob.db.fetchAll(
            "SELECT userid FROM hw_user WHERE unique_id = %(uid)s AND userid != %(userid)s AND activated = 1 LIMIT 1",
            {"uid": hashes[3], "userid": userID},
        )
    else:
        # Running under windows, full check
        logger.debug("Veryfing with Windows hardware")
        match = await glob.db.fetchAll(
            "SELECT userid FROM hw_user WHERE mac = %(mac)s AND unique_id = %(uid)s AND disk_id = %(diskid)s AND userid != %(userid)s AND activated = 1 LIMIT 1",
            {"mac": hashes[2], "uid": hashes[3], "diskid": hashes[4], "userid": userID},
        )

    if match:
        # This is a multiaccount, restrict other account and ban this account

        # Get original userID and username (lowest ID)
        originalUserID = match[0]["userid"]
        originalUsername: Optional[str] = await getUsername(originalUserID)

        # Ban this user and append notes
        await ban(userID)  # this removes the USER_PENDING_VERIFICATION flag too
        await appendNotes(
            userID,
            f"{originalUsername}'s multiaccount ({originalUserID}), found HWID match while verifying account.",
        )
        await appendNotes(
            originalUserID,
            f"Has created multiaccount {username} ({userID}).",
        )

        # Restrict the original
        await restrict(originalUserID)

        # Discord message
        await audit_logs.send_log_as_discord_webhook(
            message=f"[{originalUsername}](https://akatsuki.gg/u/{originalUserID}) has been restricted because they have created the multiaccount [{username}](https://akatsuki.gg/u/{userID}). The multiaccount has been banned.",
            discord_channel="ac_general",
        )

        # Disallow login
        return False
    else:
        # No matches found, set USER_PUBLIC and USER_NORMAL flags and reset USER_PENDING_VERIFICATION flag
        await resetPendingFlag(userID)
        # log.info("User **{}** ({}) has verified his account with hash set _{}_".format(username, userID, hashes[2:5]), 'ac_confidential')

        # Allow login
        return True


async def hasVerifiedHardware(userID: int):
    """
    Checks if `userID` has activated his account through HWID

    :param userID: user id
    :return: True if hwid activation data is in db, otherwise False
    """

    return await glob.db.fetch(
        "SELECT id FROM hw_user WHERE userid = %s " "AND activated = 1",
        [userID],
    )


async def getDonorExpire(userID: int) -> int:
    """
    Return `userID`'s donor expiration UNIX timestamp

    :param userID: user id
    :return: donor expiration UNIX timestamp
    """

    data = await glob.db.fetch(
        "SELECT donor_expire FROM users " "WHERE id = %s",
        [userID],
    )

    return data["donor_expire"] if data else 0


class invalidUsernameError(Exception):
    pass


class usernameAlreadyInUseError(Exception):
    pass


def safeUsername(username: str) -> str:
    """
    Return `username`'s safe username
    (all lowercase and underscores instead of spaces)

    :param username: unsafe username
    :return: safe username
    """

    return username.lower().strip().replace(" ", "_")


async def changeUsername(
    userID: int = 0,
    oldUsername: str = "",
    newUsername: str = "",
) -> None:
    """
    Change `userID`'s username to `newUsername` in database.

    :param userID: user id. Required only if `oldUsername` is not passed.
    :param oldUsername: username. Required only if `userID` is not passed.
    :param newUsername: new username. Can't contain spaces and underscores at the same time.
    :raise: invalidUsernameError(), usernameAlreadyInUseError()
    :return:
    """

    # Make sure new username doesn't have mixed spaces and underscores
    if " " in newUsername and "_" in newUsername:
        raise invalidUsernameError()

    # this is done twice in username command dont worry about it
    # Get safe username
    newUsernameSafe = safeUsername(newUsername)

    # Make sure this username is not already in use
    name_exists = await getIDSafe(newUsernameSafe)
    if name_exists:
        raise usernameAlreadyInUseError()

    # Get userID or oldUsername
    if not userID:
        userID = await getID(oldUsername)
    else:
        possiblyUsername = await getUsername(userID)
        assert possiblyUsername is not None
        oldUsername = possiblyUsername

    # Change username
    await glob.db.execute(
        "UPDATE users SET username = %s, username_safe = %s WHERE id = %s",
        [newUsername, newUsernameSafe, userID],
    )

    # Empty redis username cache
    # TODO: Le pipe woo woo
    await glob.redis.delete(f"ripple:userid_cache:{safeUsername(oldUsername)}")
    await glob.redis.delete(f"ripple:change_username_pending:{userID}")


async def removeFromLeaderboard(userID: int) -> None:
    """
    Removes userID from global and country leaderboards.

    :param userID:
    :return:
    """

    # Remove the user from global and country leaderboards, for every mode
    country: str = (await getCountry(userID)).lower()
    for board in ("leaderboard", "relaxboard"):
        for mode in ("std", "taiko", "ctb", "mania"):
            await glob.redis.zrem(f"ripple:{board}:{mode}", str(userID))
            if country and country != "xx":
                await glob.redis.zrem(f"ripple:{board}:{mode}:{country}", str(userID))


async def remove_from_specified_leaderboard(
    user_id: int,
    mode: int,
    relax: int,
) -> None:
    country: str = (await getCountry(user_id)).lower()

    board = {
        0: "leaderboard",
        1: "relaxboard",
        2: "autoboard",
    }[relax]
    mode_str = {
        0: "std",
        1: "taiko",
        2: "ctb",
        3: "mania",
    }[mode]

    redis_board = f"ripple:{board}:{mode_str}"

    await glob.redis.zrem(redis_board, str(user_id))
    if country and country != "xx":
        await glob.redis.zrem(f"{redis_board}:{country}", str(user_id))


async def getOverwriteWaitRemainder(userID: int) -> int:
    """
    There is a forced 60s wait between overwrites (to save server from spam to lag).

    Return the time left before the command can be used again.
    """

    raw_db_return = await glob.db.fetch(
        "SELECT previous_overwrite FROM users WHERE id = %s",
        [userID],
    )
    assert raw_db_return is not None
    return raw_db_return["previous_overwrite"]


async def removeFirstPlaces(
    userID: int,
    akat_mode: Optional[int] = None,
    game_mode: Optional[int] = None,
) -> None:
    # Go through all of the users first place scores.
    # If we find a better play, transfer the #1 to them,
    # otherwise simply delete the #1 from the db.
    q = ["SELECT scoreid, beatmap_md5, mode, rx " "FROM scores_first WHERE userid = %s"]

    if akat_mode is not None:
        q.append(f"AND rx = {akat_mode}")
    if game_mode is not None:
        q.append(f"AND mode = {game_mode}")

    for score in await glob.db.fetchAll(" ".join(q), [userID]):
        if score["rx"]:
            table = "scores_relax"
            sort = "pp"
        else:
            table = "scores"
            sort = "score"

        new = await glob.db.fetch(  # Get the 2nd top play.
            "SELECT s.id, s.userid FROM {t} s "
            "LEFT JOIN users u ON s.userid = u.id "
            "WHERE s.beatmap_md5 = %s AND s.play_mode = %s "
            "AND s.userid != %s AND s.completed = 3 AND u.privileges & 1 "
            "ORDER BY s.{s} DESC LIMIT 1".format(t=table, s=sort),
            [score["beatmap_md5"], score["mode"], userID],
        )

        if new:  # Transfer the #1 to the old #2.
            await glob.db.execute(
                "UPDATE scores_first SET scoreid = %s, userid = %s "
                "WHERE scoreid = %s",
                [new["id"], new["userid"], score["scoreid"]],
            )
        else:  # There is no 2nd place, this was the only score.
            await glob.db.execute(
                "DELETE FROM scores_first WHERE scoreid = %s",
                [score["scoreid"]],
            )


async def updateFirstPlaces(userID: int) -> None:
    # (Done for both vanilla, and relax).
    # Go through all of the users plays, check if any are #1.
    # If they are, check if theres a score in scores_first.
    # If there is, overwrite that #1 with ours, otherwise
    # add the score to scores_first.

    for rx, table_name in enumerate(("scores", "scores_relax")):
        for score in await glob.db.fetchAll(
            "SELECT s.id, s.pp, s.score, s.play_mode, "
            "s.beatmap_md5, b.ranked FROM {t} s "
            "LEFT JOIN beatmaps b USING(beatmap_md5) "
            "WHERE s.userid = %s AND s.completed = 3 "
            "AND s.score > 0 AND b.ranked > 1".format(t=table_name),
            [userID],
        ):
            # Vanilla always uses score to determine #1s.
            # Relax uses score for loved maps, and pp for other statuses.
            order = "pp" if rx and score["ranked"] != 5 else "score"

            # Get the current first place.
            firstPlace = await glob.db.fetch(
                "SELECT s.{0}, s.userid FROM {1} s "
                "LEFT JOIN users u ON s.userid = u.id "
                "WHERE s.beatmap_md5 = %s AND s.play_mode = %s "
                "AND u.privileges & 1 ORDER BY s.{0} DESC LIMIT 1".format(
                    order,
                    table_name,
                ),
                [score["beatmap_md5"], score["play_mode"]],
            )

            # Check if our score is better than the current #1.
            # If it is, then add/update scores_first.
            if (
                not firstPlace
                or score[order] > firstPlace[order]
                or userID == firstPlace["userid"]
            ):
                await glob.db.execute(
                    "REPLACE INTO scores_first " "VALUES (%s, %s, %s, %s, %s)",
                    [score["beatmap_md5"], score["play_mode"], rx, score["id"], userID],
                )


def getProfile(userID: int) -> str:
    return f"https://akatsuki.gg/u/{userID}"


async def getProfileEmbed(userID: int, clan: bool = False) -> Optional[str]:
    profile_embed = f"({await getUsername(userID)})[{getProfile(userID)}]"

    # get their clan id & tag for embed
    if clan:
        res = await glob.db.fetch(
            "SELECT c.id, c.tag FROM clans c "
            "LEFT JOIN users u ON c.id = u.clan_id "
            "WHERE u.id = %s",
            [userID],
        )

        if res:
            clan_embed = "[[https://akatsuki.gg/c/{id} {tag}]]".format(**res)
            return f"{clan_embed} {profile_embed}"

    return profile_embed
