from __future__ import annotations

import inspect
import time
from queue import Queue

import MySQLdb.cursors
from MySQLdb.connections import Connection

import settings
from common.log import logUtils as log
from objects import glob


class worker:
    """
    A single MySQL worker
    """

    __slots__ = ("connection", "temporary")

    def __init__(self, connection: Connection, temporary: bool = False):
        """
        Initialize a MySQL worker

        :param connection: database connection object
        :param temporary: if True, this worker will be flagged as temporary
        """
        self.connection = connection
        self.temporary = temporary
        log.debug(f"Created MySQL worker. Temporary: {self.temporary}")

    def ping(self):
        """
        Ping MySQL server using this worker.

        :return: True if connected, False if error occured.
        """
        c = self.connection.cursor(MySQLdb.cursors.DictCursor)
        try:
            c.execute("SELECT 1+1")
            return True
        except MySQLdb.Error:
            return False
        finally:
            c.close()

    def __del__(self):
        """
        Close connection to the server

        :return:
        """
        if self.connection.open:
            self.connection.close()


class connectionsPool:
    """
    A MySQL workers pool
    """

    __slots__ = ("config", "maxSize", "pool", "consecutiveEmptyPool")

    def __init__(self, host, username, password, database, size=128):
        """
        Initialize a MySQL connections pool

        :param host: MySQL host
        :param username: MySQL username
        :param password: MySQL password
        :param database: MySQL database name
        :param size: pool max size
        """
        self.config = (host, username, password, database)
        self.maxSize = size
        self.pool: Queue[worker] = Queue(self.maxSize)
        self.consecutiveEmptyPool = 0
        self.fillPool()

    def newWorker(self, temporary=False):
        """
        Create a new worker.

        :param temporary: if True, flag the worker as temporary
        :return: instance of worker class
        """
        db = MySQLdb.connect(
            *self.config,
            autocommit=True,
            charset="utf8",
            use_unicode=True,
        )
        conn = worker(db, temporary)
        return conn

    def fillPool(self, newConnections=0):
        """
        Fill the queue with workers

        :param newConnections:	number of new connections. If 0, the pool will be filled entirely.
        :return:
        """
        # If newConnections = 0, fill the whole pool
        if newConnections == 0:
            newConnections = self.maxSize

        # Fill the pool
        for _ in range(newConnections):
            if not self.pool.full():
                self.pool.put_nowait(self.newWorker())

    def getWorker(self, level=0):
        """
        Get a MySQL connection worker from the pool.
        If the pool is empty, a new temporary worker is created.

        :param level: number of failed connection attempts. If > 50, return None
        :return: instance of worker class
        """
        # Make sure we below 50 retries
        # log.info("Pool size: {}".format(self.pool.qsize()))
        glob.dog.increment(f"{glob.DATADOG_PREFIX}.mysql_pool.queries")
        glob.dog.gauge(f"{glob.DATADOG_PREFIX}.mysql_pool.size", self.pool.qsize())
        if level >= 50:
            log.warning(
                "Too many failed connection attempts. No MySQL connection available.",
            )
            return None

        try:
            if self.pool.empty():
                # The pool is empty. Spawn a new temporary worker
                log.warning("MySQL connections pool is empty. Using temporary worker.")
                worker = self.newWorker(True)

                # Increment saturation
                self.consecutiveEmptyPool += 1

                # If the pool is usually empty, expand it
                if self.consecutiveEmptyPool >= 10:
                    log.warning(
                        "MySQL connections pool is empty. Filling connections pool.",
                    )
                    self.fillPool()
            else:
                # The pool is not empty. Get worker from the pool
                # and reset saturation counter
                worker = self.pool.get()
                self.consecutiveEmptyPool = 0
        except MySQLdb.OperationalError:
            # Connection to server lost
            # Wait 1 second and try again
            log.warning("Can't connect to MySQL database. Retrying in 1 second...")
            glob.dog.increment(f"{glob.DATADOG_PREFIX}.mysql_pool.failed_connections")
            time.sleep(1)
            return self.getWorker(level=level + 1)

        # Return the connection
        return worker

    def putWorker(self, worker):
        """
        Put the worker back in the pool.
        If the worker is temporary, close the connection
        and destroy the object

        :param worker: worker object
        :return:
        """
        if worker.temporary or self.pool.full():
            # Kill the worker if it's temporary or the queue
            # is full and we can't  put anything in it
            del worker
        else:
            # Put the connection in the queue if there's space
            self.pool.put_nowait(worker)


class db:
    """
    A MySQL helper with multiple workers
    """

    __slots__ = ("pool",)

    def __init__(self, host, username, password, database, initialSize):
        """
        Initialize a new MySQL database helper with multiple workers.
        This class is thread safe.

        :param host: MySQL host
        :param username: MySQL username
        :param password: MySQL password
        :param database: MySQL database name
        :param initialSize: initial pool size
        """
        self.pool = connectionsPool(host, username, password, database, initialSize)

    def execute(self, query, params=None):
        """
        Executes a query

        :param query: query to execute. You can bind parameters with %s
        :param params: parameters list. First element replaces first %s and so on
        """
        if settings.DEBUG:
            # print sql queries
            stack = []
            for frame in inspect.stack()[1:]:
                if frame.function == "handle":  # TODO: better
                    break
                stack.append(frame.function)
            delim = " \x1b[0;92m->\x1b[0m "
            print(f"execute ({delim.join(reversed(stack))})")

        if params is None:
            params = ()
        cursor = None
        worker = self.pool.getWorker()
        if worker is None:
            return None
        try:
            # Create cursor, execute query and commit
            cursor = worker.connection.cursor(MySQLdb.cursors.DictCursor)
            cursor.execute(query, params)
            log.debug(query)
            return cursor.lastrowid
        finally:
            # Close the cursor and release worker's lock
            if cursor:
                cursor.close()
            if worker:
                self.pool.putWorker(worker)

    def fetch(self, query, params=None, _all=False):
        """
        Fetch a single value from db that matches given query

        :param query: query to execute. You can bind parameters with %s
        :param params: parameters list. First element replaces first %s and so on
        :param _all: fetch one or all values. Used internally. Use fetchAll if you want to fetch all values
        """
        if settings.DEBUG:
            # print sql queries
            stack = []
            for frame in inspect.stack()[1:]:
                if frame.function == "handle":  # TODO: better
                    break
                stack.append(frame.function)
            delim = " \x1b[0;92m->\x1b[0m "
            print(f"fetch ({delim.join(reversed(stack))})")

        if params is None:
            params = ()
        cursor = None
        worker = self.pool.getWorker()
        if worker is None:
            return None
        try:
            # Create cursor, execute the query and fetch one/all result(s)
            cursor = worker.connection.cursor(MySQLdb.cursors.DictCursor)
            cursor.execute(query, params)
            log.debug(query)
            if _all:
                return cursor.fetchall()
            else:
                return cursor.fetchone()
        finally:
            # Close the cursor and release worker's lock
            if cursor:
                cursor.close()
            if worker:
                self.pool.putWorker(worker)

    def fetchAll(self, query, params=None):
        """
        Fetch all values from db that match given query.
        Calls self.fetch with all = True.

        :param query: query to execute. You can bind parameters with %s
        :param params: parameters list. First element replaces first %s and so on
        """
        if params is None:
            params = ()
        return self.fetch(query, params, _all=True)
