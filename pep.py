#!/usr/bin/env python3.9

import os
import sys
import threading
from datetime import datetime as dt
from multiprocessing.pool import ThreadPool

import redis
import tornado.gen
import tornado.httpserver
import tornado.ioloop
import tornado.web
from raven.contrib.tornado import AsyncSentryClient

from cmyui.logging import Ansi, log, printc
from common import agpl, generalUtils
from common.constants import bcolors
from common.db import dbConnector
from common.ddog import datadogClient
from common.redis import pubSub
from handlers import (apiFokabotMessageHandler, apiIsOnlineHandler,
                      apiOnlineUsersHandler, apiServerStatusHandler,
                      apiVerifiedStatusHandler, ciTriggerHandler, mainHandler)
from helpers import configHelper, consoleHelper
from helpers import systemHelper as system
from irc import ircserver
from objects import banchoConfig, fokabot, glob
from pubSubHandlers import (banHandler, changeUsernameHandler,
                            disconnectHandler, notificationHandler,
                            unbanHandler, updateSilenceHandler,
                            updateStatsHandler, wipeHandler)


def make_app():
    return tornado.web.Application([
        (r'/', mainHandler.handler),
        (r'/api/v1/isOnline', apiIsOnlineHandler.handler),
        (r'/api/v1/onlineUsers', apiOnlineUsersHandler.handler),
        (r'/api/v1/serverStatus', apiServerStatusHandler.handler),
        (r'/api/v1/ciTrigger', ciTriggerHandler.handler),
        (r'/api/v1/verifiedStatus', apiVerifiedStatusHandler.handler),
        (r'/api/v1/fokabotMessage', apiFokabotMessageHandler.handler)
    ])

ASCII_LOGO = '\n'.join([
    '      _/_/    _/                    _/                          _/        _/',
    '   _/    _/  _/  _/      _/_/_/  _/_/_/_/    _/_/_/  _/    _/  _/  _/',
    '  _/_/_/_/  _/_/      _/    _/    _/      _/_/      _/    _/  _/_/      _/',
    ' _/    _/  _/  _/    _/    _/    _/          _/_/  _/    _/  _/  _/    _/',
    '_/    _/  _/    _/    _/_/_/      _/_/  _/_/_/      _/_/_/  _/    _/  _/'
])

if __name__ == "__main__":
    # AGPL license agreement
    try:
        agpl.check_license("ripple", "pep.py")
    except agpl.LicenseError as e:
        print(str(e))
        sys.exit(1)

    try:
        # Server start
        printc(ASCII_LOGO, Ansi.LGREEN)
        log(f'Welcome to pep.py osu!bancho server v{glob.VERSION}', Ansi.LGREEN)
        log('Made by the Ripple and Akatsuki teams', Ansi.LGREEN)
        log(f'{bcolors.UNDERLINE}https://github.com/osuAkatsuki/pep.py', Ansi.LGREEN)
        log('Press CTRL+C to exit\n', Ansi.LGREEN)
        os.chdir(os.path.dirname(os.path.realpath(__file__)))

        glob.conf = configHelper.config('config.ini')

        if glob.conf.default:
            # We have generated a default config.ini, quit server
            log('A default config has been generated.', Ansi.LGREEN)
            sys.exit()

        # If we haven't generated a default config.ini, check if it's valid
        if not glob.conf.checkConfig():
            log('Invalid config file.', Ansi.LRED)
            sys.exit()

        log('Ensuring folders.', Ansi.LMAGENTA)
        if not os.path.exists('.data'):
            os.makedirs('.data', 0o770)

        # Connect to db
        try:
            log('Connecting to SQL.', Ansi.LMAGENTA)
            glob.db = dbConnector.db(
                glob.conf.config["db"]["host"],
                glob.conf.config["db"]["username"],
                glob.conf.config["db"]["password"],
                glob.conf.config["db"]["database"],
                int(glob.conf.config["db"]["workers"])
            )
        except :
            log(f'Error connecting to sql.', Ansi.LRED)
            raise

        # Connect to redis
        try:
            log('Connecting to redis.', Ansi.LMAGENTA)
            glob.redis = redis.Redis(
                glob.conf.config["redis"]["host"],
                glob.conf.config["redis"]["port"],
                glob.conf.config["redis"]["database"],
                glob.conf.config["redis"]["password"]
            )
            glob.redis.ping()
        except:
            log(f'Error connecting to redis.', Ansi.LRED)
            raise

        # Empty redis cache
        try:
            glob.redis.set("ripple:online_users", 0)
            glob.redis.eval("return redis.call('del', unpack(redis.call('keys', ARGV[1])))", 0, "peppy:*")
        except redis.exceptions.ResponseError:
            # Script returns error if there are no keys starting with peppy:*
            pass

        # Save peppy version in redis
        glob.redis.set("peppy:version", glob.VERSION)

        # Load bancho_settings
        try:
            glob.banchoConf = banchoConfig.banchoConfig()
        except:
            log(f'Error loading bancho settings.', Ansi.LMAGENTA)
            raise

        # Delete old bancho sessions
        glob.tokens.deleteBanchoSessions()

        # Create threads pool
        try:
            glob.pool = ThreadPool(int(glob.conf.config["server"]["threads"]))
        except ValueError:
            log(f'Error creating threads pool.', Ansi.LRED)
            consoleHelper.printError()
            consoleHelper.printColored("[!] Error while creating threads pool. Please check your config.ini and run the server again", bcolors.RED)
            raise

        # Get build date for login notifications
        with open('build.date', 'r') as f:
            timestamp = dt.utcfromtimestamp(int(f.read()))
            glob.latestBuild = timestamp.strftime('%b %d %Y')

        log(f'Connecting {glob.BOT_NAME}', Ansi.LMAGENTA)
        fokabot.connect()

        glob.channels.loadChannels()

        # Initialize stremas
        glob.streams.add("main")
        glob.streams.add("lobby")

        log('Starting background loops.', Ansi.LMAGENTA)

        glob.tokens.usersTimeoutCheckLoop()
        glob.tokens.spamProtectionResetLoop()
        glob.matches.cleanupLoop()

        glob.localize = generalUtils.stringToBool(glob.conf.config["localize"]["enable"])
        if not glob.localize:
            log('User localization is disabled.', Ansi.LYELLOW)

        glob.gzip = generalUtils.stringToBool(glob.conf.config["server"]["gzip"])
        glob.gziplevel = int(glob.conf.config["server"]["gziplevel"])
        if not glob.gzip:
            log('Gzip compression is disabled.', Ansi.LYELLOW)

        glob.debug = generalUtils.stringToBool(glob.conf.config["debug"]["enable"])
        glob.outputPackets = generalUtils.stringToBool(glob.conf.config["debug"]["packets"])
        glob.outputRequestTime = generalUtils.stringToBool(glob.conf.config["debug"]["time"])
        if glob.debug:
            log('Server running in debug mode.', Ansi.LYELLOW)

        glob.application = make_app()

        # set up sentry
        try:
            glob.sentry = generalUtils.stringToBool(glob.conf.config["sentry"]["enable"])
            if glob.sentry:
                glob.application.sentry_client = AsyncSentryClient(
                    glob.conf.config["sentry"]["banchodsn"],
                    release = glob.VERSION
                )
        except:
            log('Error creating sentry client.', Ansi.LRED)
            raise

        # set up datadog
        try:
            if generalUtils.stringToBool(glob.conf.config["datadog"]["enable"]):
                glob.dog = datadogClient.datadogClient(
                    glob.conf.config["datadog"]["apikey"],
                    glob.conf.config["datadog"]["appkey"],
                    [
                        datadogClient.periodicCheck("online_users", lambda: len(glob.tokens.tokens)),
                        datadogClient.periodicCheck("multiplayer_matches", lambda: len(glob.matches.matches)),

                        #datadogClient.periodicCheck("ram_clients", lambda: generalUtils.getTotalSize(glob.tokens)),
                        #datadogClient.periodicCheck("ram_matches", lambda: generalUtils.getTotalSize(glob.matches)),
                        #datadogClient.periodicCheck("ram_channels", lambda: generalUtils.getTotalSize(glob.channels)),
                        #datadogClient.periodicCheck("ram_file_buffers", lambda: generalUtils.getTotalSize(glob.fileBuffers)),
                        #datadogClient.periodicCheck("ram_file_locks", lambda: generalUtils.getTotalSize(glob.fLocks)),
                        #datadogClient.periodicCheck("ram_datadog", lambda: generalUtils.getTotalSize(glob.datadogClient)),
                        #datadogClient.periodicCheck("ram_verified_cache", lambda: generalUtils.getTotalSize(glob.verifiedCache)),
                        #datadogClient.periodicCheck("ram_irc", lambda: generalUtils.getTotalSize(glob.ircServer)),
                        #datadogClient.periodicCheck("ram_tornado", lambda: generalUtils.getTotalSize(glob.application)),
                        #datadogClient.periodicCheck("ram_db", lambda: generalUtils.getTotalSize(glob.db)),
                    ])
        except:
            log('Error creating datadog client.', Ansi.LRED)
            raise

        # start irc server if configured
        glob.irc = generalUtils.stringToBool(glob.conf.config["irc"]["enable"])
        if glob.irc:
            try:
                ircPort = int(glob.conf.config["irc"]["port"])
            except ValueError:
                log('Invalid IRC port.', Ansi.LRED)
                raise

            log(f'IRC server listening on 127.0.0.1:{ircPort}.', Ansi.LMAGENTA)
            threading.Thread(target = lambda: ircserver.main(port = ircPort)).start()

        # fetch priv groups (optimization by cmyui)
        glob.groupPrivileges = {row['name'].lower(): row['privileges'] for row in
            glob.db.fetchAll(
                'SELECT name, privileges '
                'FROM privileges_groups'
            )
        }

        try:
            serverPort = int(glob.conf.config["server"]["port"])
        except ValueError:
            log(f'Invalid server port.', Ansi.LRED)
            raise

        # Server start message and console output
        log(f'Tornado listening for HTTP(s) clients on 127.0.0.1:{serverPort}.', Ansi.LMAGENTA)

        # Connect to pubsub channels
        pubSub.listener(glob.redis, {
            "peppy:ban": banHandler.handler(),
            "peppy:unban": unbanHandler.handler(),
            "peppy:silence": updateSilenceHandler.handler(),

            "peppy:disconnect": disconnectHandler.handler(),
            "peppy:notification": notificationHandler.handler(),
            "peppy:change_username": changeUsernameHandler.handler(),
            "peppy:update_cached_stats": updateStatsHandler.handler(),

            "peppy:wipe": wipeHandler.handler(),

            "peppy:reload_settings": lambda x: x == b"reload" and glob.banchoConf.reload(),
        }).start()

        # Start tornado
        glob.application.listen(serverPort)
        tornado.ioloop.IOLoop.instance().start()
    finally:
        system.dispose()
