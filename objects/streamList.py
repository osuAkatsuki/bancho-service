from typing import TYPE_CHECKING

from objects import glob, stream

if TYPE_CHECKING:
    from typing import Optional

    from objects.osuToken import token

# TODO: use *args and **kwargs
class streamList:
    __slots__ = ('streams',)

    def __init__(self):
        self.streams = {}

    def add(self, name: str) -> None:
        """
        Create a new stream list if it doesn't already exist

        :param name: stream name
        :return:
        """
        if name not in self.streams:
            self.streams[name] = stream.stream(name)

    def remove(self, name: str) -> None:
        """
        Removes an existing stream and kick every user in it

        :param name: stream name
        :return:
        """
        if name in self.streams:
            for i in self.streams[name].clients:
                if i in glob.tokens.tokens:
                    glob.tokens.tokens[i].leaveStream(name)
            self.streams.pop(name)


    def join(
        self, name: str, client: 'Optional[token]' = None,
        token: 'Optional[str]' = None
    ) -> None:
        """
        Add a client to a stream

        :param name: stream name
        :param client: client (osuToken) object
        :param token: client uuid string
        :return:
        """
        if name in self.streams:
            self.streams[name].addClient(client=client, token=token)

    def leave(
        self, name: str, client: 'Optional[token]' = None,
        token: 'Optional[str]' = None
    ) -> None:
        """
        Remove a client from a stream

        :param name: stream name
        :param client: client (osuToken) object
        :param token: client uuid string
        :return:
        """
        if name in self.streams:
            self.streams[name].removeClient(client=client, token=token)

    def broadcast(self, name: str, data: bytes, but: list[str] = []) -> None:
        """
        Send some data to all clients in a stream

        :param name: stream name
        :param data: data to send
        :param but: array of tokens to ignore. Default: None (send to everyone)
        :return:
        """
        if name in self.streams:
            self.streams[name].broadcast(data, but)

    def broadcast_limited(self, name: str, data: bytes, users: list[str]) -> None:
        """
        Send some data to specific clients in a stream

        :param name: stream name
        :param data: data to send
        :param users: array of tokens to broadcast to
        :return:
        """
        if name in self.streams:
            self.streams[name].broadcast_limited(data, users)

    def dispose(self, name: str, *args, **kwargs) -> None:
        """
        Call `dispose` on `name`

        :param name: name of the stream
        :param args:
        :param kwargs:
        :return:
        """
        if name in self.streams:
            self.streams[name].dispose(*args, **kwargs)

    def getStream(self, name: str) -> 'Optional[stream.stream]':
        """
        Returns name's stream object or None if it doesn't exist

        :param name:
        :return:
        """
        if name in self.streams:
            return self.streams[name]
