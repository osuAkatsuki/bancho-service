from typing import TYPE_CHECKING

from objects import glob

if TYPE_CHECKING:
    from typing import Optional

    from objects.osuToken import token

class stream:
    __slots__ = ('name', 'clients')
    def __init__(self, name: str) -> None:
        """
        Initialize a stream object

        :param name: stream name
        """
        self.name = name
        self.clients = []

    def addClient(
        self, client: 'Optional[token]' = None,
        token: 'Optional[str]' = None
    ) -> None:
        """
        Add a client to this stream if not already in

        :param client: client (osuToken) object
        :param token: client uuid string
        :return:
        """
        if not (client or token):
            return

        if client:
            token = client.token

        if token not in self.clients:
            #log.info("{} has joined stream {}.".format(token, self.name))
            self.clients.append(token)

    def removeClient(
        self, client: 'Optional[token]' = None,
        token: 'Optional[str]' = None
    ) -> None:
        """
        Remove a client from this stream if in

        :param client: client (osuToken) object
        :param token: client uuid string
        :return:
        """
        if not (client or token):
            return

        if client:
            token = client.token

        if token in self.clients:
            #log.info("{} has left stream {}.".format(token, self.name))
            self.clients.remove(token)

    def broadcast(self, data: bytes, but: list[str] = []) -> None:
        """
        Send some data to all (or some) clients connected to this stream

        :param data: data to send
        :param but: array of tokens to ignore. Default: None (send to everyone)
        :return:
        """
        for i in self.clients:
            if i in glob.tokens.tokens:
                if i not in but:
                    glob.tokens.tokens[i].enqueue(data)
            else:
                self.removeClient(token=i)

    def broadcast_limited(self, data: bytes, users: list[str]) -> None:
        """
        Send some data to specific clients connected to this stream

        :param data: data to send
        :param users: array of tokens broadcast to.
        :return:
        """
        for i in self.clients:
            if i in glob.tokens.tokens:
                if i in users:
                    glob.tokens.tokens[i].enqueue(data)
            else:
                self.removeClient(token=i)

    def dispose(self) -> None:
        """
        Tell every client in this stream to leave the stream

        :return:
        """
        for i in self.clients:
            if i in glob.tokens.tokens:
                glob.tokens.tokens[i].leaveStream(self.name)
