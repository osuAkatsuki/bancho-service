from __future__ import annotations

from threading import Lock


class fileLocks:
    __slots__ = ("locks",)

    def __init__(self) -> None:
        # Dictionary containing threading.Lock s
        self.locks = {}

    def lockFile(self, fileName: str) -> None:
        """
        Set a file as locked.

        :param fileName: file name
        :return:
        """
        if fileName in self.locks:
            # Acquire existing lock
            self.locks[fileName].acquire()
        else:
            # Create new lock and acquire it
            self.locks[fileName] = Lock()
            self.locks[fileName].acquire()

    def unlockFile(self, fileName: str) -> None:
        """
        Unlock a previously locked file

        :param fileName: file name
        :return:
        """
        if fileName in self.locks:
            # Release lock if it exists
            self.locks[fileName].release()
