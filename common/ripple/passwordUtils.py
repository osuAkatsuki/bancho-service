from __future__ import annotations

import bcrypt


def checkOldPassword(password: str, salt: str, rightPassword: str) -> bool:
    """
    Check if `password` + `salt` corresponds to `rightPassword`
    NOT USED ANYMORE! RETURNS ALWAYS FALSE!

    :param password: input password
    :param salt: password's salt
    :param rightPassword: tight password
    :return: True if the password is correct, otherwise False.
    """
    return False
    # return (rightPassword == crypt.crypt(password, "$2y$"+str(base64.b64decode(salt))))


def checkNewPassword(password: str, dbPassword: str) -> bool:
    """
    Check if a password (version 2) is right.

    :param password: input password
    :param dbPassword: the password in the database
    :return: True if the password is correct, otherwise False.
    """
    if len(password) != 32:
        return False

    password = password.encode("utf-8")
    dbPassword = dbPassword.encode("utf-8")
    return bcrypt.checkpw(password, dbPassword)


def genBcrypt(password: str) -> bytes:
    """
    Bcrypts a password.

    :param password: the password to hash
    :return: bytestring
    """
    return bcrypt.hashpw(password.encode("utf8"), bcrypt.gensalt(10, b"2a"))
