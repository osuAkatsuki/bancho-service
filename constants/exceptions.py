class loginFailedException(Exception):
    pass

class loginBannedException(Exception):
    pass

class tokenNotFoundException(Exception):
    pass

class channelNoPermissionsException(Exception):
    pass

class channelUnknownException(Exception):
    pass

class channelModeratedException(Exception):
    pass

class banchoMaintenanceException(Exception):
    pass

class moderatedPMException(Exception):
    pass

class userNotFoundException(Exception):
    pass

class stopSpectating(Exception):
    pass

class matchWrongPasswordException(Exception):
    pass

class matchNotFoundException(Exception):
    pass

class matchCreateError(Exception):
    pass

class banchoRestartingException(Exception):
    pass

class invalidArgumentsException(Exception):
    pass

class userSilencedException(Exception):
    pass

class userBlockingDMsException(Exception):
    pass

class need2FAException(Exception):
    pass

class userRestrictedException(Exception):
    pass

class haxException(Exception):
    pass

class forceUpdateException(Exception):
    pass

class loginLockedException(Exception):
    pass

class userTournamentException(Exception):
    pass

class userAlreadyInChannelException(Exception):
    pass

class userNotInChannelException(Exception):
    pass

class missingReportInfoException(Exception):
    pass

class invalidUserException(Exception):
    pass

class wrongChannelException(Exception):
    pass

class periodicLoopException(Exception):
    pass
